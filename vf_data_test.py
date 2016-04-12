#!/usr/bin/env python3
import os
import pickle
import vf_data


def main():
    '''
    with open("datasets/vfdb/418", "rb") as f:
        sampling_rate = pickle.load(f)
        signals = pickle.load(f)
        annotations = pickle.load(f)
        print(sampling_rate, len(signals))
        for annotation in annotations:
            print(annotation)
    '''

    record = vf_data.Record()
    record.load("vfdb", "418")
    segments = record.get_segments()
    for segment in segments:
        print(segment.begin_time, segment.has_vf)

    return 0

if __name__ == '__main__':
    main()
