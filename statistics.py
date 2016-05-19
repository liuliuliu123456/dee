#!/usr/bin/env python3
import pyximport; pyximport.install()
import vf_data
import argparse

COARSE_VF_THRESHOLD = 0.2

rhythm_name_tab = """
(AFIB	atrial fibrillation
(AF	atrial fibrillation
(ASYS	asystole
(B	ventricular bigeminy
(BI	first degree heart block
(HGEA	high grade ventricular ectopic activity
(N	normal sinus rhythm
(NSR	normal sinus rhythm
(NOD	nodal ("AV junctional") rhythm
(NOISE	noise
(PM	pacemaker (paced rhythm)
(SBR	sinus bradycardia
(SVTA	supraventricular tachyarrhythmia
(VER	ventricular escape rhythm
(VF	ventricular fibrillation
(VFL	ventricular flutter
(VT ventricular tachycardia
(AB	Atrial bigeminy
(AFIB		Atrial fibrillation
(AFL		Atrial flutter
(B		Ventricular bigeminy
(BII		2° heart block
(IVR		Idioventricular rhythm
(N		Normal sinus rhythm
(NOD		Nodal (A-V junctional) rhythm
(P		Paced rhythm
(PREX		Pre-excitation (WPW)
(SBR		Sinus bradycardia
(SVTA		Supraventricular tachyarrhythmia
(T		Ventricular trigeminy
(B3	Third degree heart block
(SAB	Sino-atrial block
(VT.r	Ventricular tachycardia (rapid)
(VT.s	Ventricular tachycardia (slow)
(VT.o	Ventricular tachycardia (other)
(VF.c	ventricular fibrillation (coarse)
(VF.f	ventricular fibrillation (fine)
"""
rhythm_descriptions = {}
for line in rhythm_name_tab.strip().split("\n"):
    cols = line.split("\t", maxsplit=1)
    if len(cols) > 1:
        name = cols[0].strip()
        desc = cols[1].strip()
        rhythm_descriptions[name] = desc


def main():
    # parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--db-names", type=str, nargs="+", default=None)
    # parser.add_argument("-o", "--output", type=str)
    parser.add_argument("-s", "--segment-duration", type=int, default=8)
    parser.add_argument("-c", "--correction-file", type=str, help="Override the incorrect labels of the original dataset.")
    args = parser.parse_args()

    n_segments = 0
    rhythm_statistics = {}
    case_statistics = {}
    dataset = vf_data.DataSet()
    if args.correction_file:
        dataset.load_correction(args.correction_file)
    for segment in dataset.get_samples(args.segment_duration):
        info = segment.info
        db_name = info.record_name.split("/", maxsplit=1)[0]
        if args.db_names and (db_name not in args.db_names):
            continue
        rhythm_name = info.rhythm
        # print(info.record_name, info.begin_time, info.rhythm_types)
        # distinguish subtypes of VT and VF
        if rhythm_name == "(VF":
            if info.amplitude > COARSE_VF_THRESHOLD:  # coarse VF
                rhythm_name = "(VF.c"
            else:
                rhythm_name = "(VF.f"
        elif rhythm_name == "(VT":
            hr = info.get_heart_rate()
            if hr == 0:
                rhythm_name = "(VT.o"
            elif hr > 180:
                rhythm_name = "(VT.r"
            else:
                rhythm_name = "(VT.s"
        rhythm_statistics[rhythm_name] = rhythm_statistics.get(rhythm_name, 0) + 1
        case_statistics.setdefault(rhythm_name, set()).add(info.record_name)
        n_segments += 1

    print("name\tsamples\tcases\tdescription")
    for name in sorted(rhythm_statistics.keys()):
        desc = rhythm_descriptions.get(name, name)
        n_samples = rhythm_statistics[name]
        n_cases = len(case_statistics[name])
        print(name, "\t", n_samples, "\t", n_cases, "\t", desc)
    print("\t", n_segments, "ECG segments")


if __name__ == "__main__":
    main()
