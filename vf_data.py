#!/usr/bin/env python2
from ctypes import *
import numpy as np
import scipy.signal
import os
import wfdb
from vf_features import extract_features
# import pickle
import cPickle as pickle  # python 2 only
from multiprocessing import Pool


DEFAULT_SAMPLING_RATE = 360.0
N_JOBS = 4


# get name of records from a database
def get_records(db_name):
    records = []
    dirname = os.path.expanduser("~/database/{0}".format(db_name))
    for name in os.listdir(dirname):
        if name.endswith(".dat"):
            record = os.path.splitext(name)[0]
            records.append(record)
    records.sort()
    return records


class Segment:
    def __init__(self):
        self.record = ""
        self.label = 0
        self.signals = None
        self.begin_time = 0
        self.duration = 0


class Record:
    def __init__(self):
        self.signals = []
        self.annotations = []
        self.name = ""
        self.sample_rate = 0

    def load(self, db_name, record):
        record_name = "{0}/{1}".format(db_name, record)
        self.name = record_name

        # query number of channels in this record
        n_channels = wfdb.isigopen(record_name, None, 0)

        # query sampling rate of the record
        self.sample_rate = wfdb.sampfreq(record_name)

        # read the signals
        sigInfo = (wfdb.WFDB_Siginfo * n_channels)()
        sample_buf = (wfdb.WFDB_Sample * n_channels)()
        signals = []
        if wfdb.isigopen(record_name, byref(sigInfo), n_channels) == n_channels:
            while wfdb.getvec(byref(sample_buf)) > 0:
                sample = sample_buf[0]  # we only want the first channel
                signals.append(sample)
        signals = np.array(signals)

        # read annotations
        annotations = []
        ann_name = wfdb.String("atr")
        ann_info = (wfdb.WFDB_Anninfo * n_channels)()
        for item in ann_info:
            item.name = ann_name
            item.stat = wfdb.WFDB_READ
        if wfdb.annopen(record_name, byref(ann_info), n_channels) == 0:
            ann_buf = (wfdb.WFDB_Annotation * n_channels)()
            while wfdb.getann(0, byref(ann_buf)) == 0:
                ann = ann_buf[0]  # we only want the first channel
                ann_code = ord(ann.anntyp)
                rhythm_type = ""
                if ann.aux:
                    # the first byte of aux is the length of the string
                    aux_ptr = cast(ann.aux, c_void_p).value + 1  # skip the first byte
                    rhythm_type = cast(aux_ptr, c_char_p).value
                # print ann.time, wfdb.anndesc(ann_code), wfdb.annstr(ann_code), rhythm_type
                annotations.append((ann.time, wfdb.annstr(ann_code), rhythm_type))

        self.signals = signals
        self.annotations = annotations

    def get_total_time(self):
        return len(self.signals) / self.sample_rate

    # perform segmentation
    def get_segments(self, duration=8.0):
        n_samples = len(self.signals)
        segment_size = int(self.sample_rate * duration)
        n_segments = int(np.floor(n_samples / segment_size))
        segments = []
        labels = []

        annotations = self.annotations
        n_annotations = len(annotations)
        i_ann = 0
        in_vf_episode = False
        # in_noise = False
        for i_seg in range(n_segments):
            # split the segment
            segment_begin = i_seg * segment_size
            segment_end = segment_begin + segment_size
            segment = self.signals[segment_begin:segment_end]
            segments.append(segment)
            contains_vf = in_vf_episode  # label of the segment
            has_noise = False
            # handle annotations belonging to this segment
            while i_ann < n_annotations:
                ann_time, code, rhythm_type = annotations[i_ann]
                if ann_time < segment_end:
                    if in_vf_episode:  # current rhythm is Vf
                        if code == "]" or not rhythm_type.startswith("(V"):  # end of Vf found
                            in_vf_episode = False
                    else:  # current rhythm is not Vf
                        if code == "[" or rhythm_type.startswith("(V"):  # begin of Vf found
                            contains_vf = in_vf_episode = True
                    i_ann += 1
                else:
                    break
            labels.append(1 if contains_vf else 0)
        return np.array(segments), np.array(labels)


def extract_features_job(s):
    db_name, record_name, segment, sample_rate = s
    return extract_features(segment, sampling_rate=DEFAULT_SAMPLING_RATE)


def load_all_segments():
    segments_cache_name = "all_segments.dat"
    segment_duration = 8  # 8 sec per segment
    all_segments = []
    all_labels = []
    # load cached segments if they exist
    try:
        with open(segments_cache_name, "rb") as f:
            all_segments = pickle.load(f)
            all_labels = pickle.load(f)
    except Exception:
        pass

    if not all_segments or not all_labels:
        # mitdb and vfdb contain two channels, but we only use the first one here
        # data source sampling rate:
        # mitdb: 360 Hz
        # vfdb, cudb: 250 Hz
        output = open("summary.csv", "w")
        output.write('"db", "record", "vf", "non-vf"\n')
        for db_name in ("mitdb", "vfdb", "cudb"):
            for record_name in get_records(db_name):
                print "read record:", db_name, record_name
                record = Record()
                record.load(db_name, record_name)

                print "  sample rate:", record.sample_rate, "# of samples:", len(record.signals), ", # of anns:", len(record.annotations)

                segments, labels = record.get_segments(segment_duration)
                print "  segments:", len(segments), ", segment size:", len(segments[0])
                print "  # of vf segments (label=1):", np.sum(labels)

                n_vf = np.sum(labels)
                n_non_vf = len(segments) - n_vf
                output.write('"{0}","{1}",{2},{3}\n'.format(db_name, record_name, n_vf, n_non_vf))

                for segment in segments:
                    # resample to DEFAULT_SAMPLING_RATE as needed
                    if record.sample_rate != DEFAULT_SAMPLING_RATE:
                        segment = scipy.signal.resample(segment, DEFAULT_SAMPLING_RATE * segment_duration)

                    all_segments.append((db_name, record_name, segment, record.sample_rate))
                all_labels.extend(labels)

        '''
        for segment, has_vf in zip(all_segments, all_labels):
            if has_vf:
                plt.plot(segment[2])
                plt.show()
        '''

        wfdb.wfdbquit()
        output.close()

        # cache the segments
        try:
            with open(segments_cache_name, "wb") as f:
                pickle.dump(all_segments, f)
                pickle.dump(all_labels, f)
        except Exception:
            pass

    return all_segments, all_labels


def load_data():
    features_cache_name = "features.dat"
    x_data = []
    y_data = []
    # load cached segments if they exist
    try:
        with open(features_cache_name, "rb") as f:
            x_data = pickle.load(f)
            y_data = pickle.load(f)
    except Exception:
        all_segments, all_labels = load_all_segments()

        # use multiprocessing for speed up.
        print "start feature extraction..."
        pool = Pool(N_JOBS)
        x_data = pool.map(extract_features_job, all_segments)
        '''
        x_data = []
        for db_name, record_name, segment, sample_rate in all_segments:
            # convert segment values to features
            x_data.append(extract_features(segment, sampling_rate=sample_rate))
        '''
        x_data = np.array(x_data)
        y_data = np.array(all_labels)

        # cache the data
        try:
            with open(features_cache_name, "wb") as f:
                pickle.dump(x_data, f)
                pickle.dump(y_data, f)
        except Exception:
            pass
        print "features are extracted."

    return x_data, y_data
