def read_raw(setup, sheet):
    import mne
    from mne import io
    import os
    import pandas as pd
    from pyentrp import entropy as ent
    import numpy as np
    from functional import map_stag_with_raw, my_rename_col, order_channels
    from config import raw_path, stag_fname, mysave, pe_par

    fnames_ = sorted(np.array(filter(lambda x: x.endswith('.edf'), os.listdir(raw_path))))
    fnames = [i.split('.edf')[0] for i in fnames_] #delete .edf from fname
    #just for counting
    fnames_100_ = [i for i in fnames if '_ref100' in i]
    fnames_100_1_ = [i for i in fnames_100_ if '_1_' in i]
    fnames_100_2_ = [i for i in fnames_100_ if '_2_' in i]

    s = pd.read_excel(stag_fname, sheetname=sheet)
    s = my_rename_col(s)
    s = s.drop(s.columns[[0, 1, 2]], axis=1) #drop cols like 'Condition', 'Minuten', etc
    #set pe parameters
    if setup != 'psd':
        embed = pe_par[setup]['embed']
        tau = pe_par[setup]['tau']
    #set typ_name for saving
    if setup.startswith('pe'):
        typ_name = 'pet' + str(tau) + 'm' + str(embed)
    elif setup.startswith('mspe'):
        typ_name = 'mspet' + str(tau) + 'm' + str(embed)
    elif setup == 'psd':
        typ_name = setup
    # set bad sbjs, defined by inspecting excell dat (e.g red annotations by Heidi)
    if sheet == 'St_Pr_corrected_27min':
        #bad = ['205_1_S', '206_1_S', '208_1_S', '211_1_S', '211_2_S', '212_2_S', '213_1_S',
        #'213_2_S', '214_1_S', '214_2_S', '218_1_S', '220_1_S', '220_2_S', '221_1_S', '226_1_S', '227_2_S',
        #'231_2_S', '232_1_S', '232_2_S', '235_1_S', '238_1_S', '239_1_S']
        bad = ['205_1_S', '206_1_S', '208_1_S', '213_1_S', '238_1_S', '239_1_S']

    elif sheet == 'Staging_vs_Prechtl_27min':
        bad = ['205_1', '206_1', '207_1_S', '207_2_S', '208_1', '211_1.1heog?', '212_2,2heogref100',
                '213_1', '213_2,1heog', '213_2.2heogsref100', '214_1,2heogsref100', '214_2,2heogsref100',
                '218_1,1heog', '220_2.2heogref100', '221_12heogref100', '221_1.1heog', '222_1,2heogsref100',
                '223_1,2heogsref100', '226_1.2heogsref100', '226_2,1heog', '226_2,2heogref100', '227_2,1heog',
                '231_2,1heog', '232_1', '232_2,1heog', '235_1,2heogsref100', '235_1,1heog', '238_1', '239_1']
    else: bad = []

    def preproces(raw):
        raw.pick_types(eeg=True)
        raw.filter(l_freq=1., h_freq=30., fir_design='firwin')
        return raw

    def load_raw_and_stag(idf_stag, idf_raw):
        stag = s.filter(like = idf_stag)
        raw = io.read_raw_edf(raw_path + idf_raw + '.edf', preload=True, \
                            stim_channel=None)

        return preproces(raw), stag # apply pp.
        #return raw, stag #no pp.

    def compute_pe_segm(raw, embed=3, tau=1, window=30, mspe=False):
        data = raw.get_data()
        sfreq = raw.info['sfreq']
        length_dp = len(raw.times)
        window_dp = int(window*sfreq)
        no_epochs = int(length_dp // window_dp)
        chan_len = len(raw.ch_names)
        store_segm = []
        if mspe:
            scale = 5
            m = np.zeros((scale, chan_len, no_epochs)) # multiscale entropy
        else:
            m = np.zeros((chan_len, no_epochs)) # PE
        for i in range(no_epochs):
            e_ = data[...,:window_dp]
            print e_.shape
            data = np.delete(data, np.s_[:window_dp], axis =1 )
            for j in range(chan_len):
                if mspe:
                    m[:,j,i] = ent.multiscale_permutation_entropy(e_[j], m=3, delay=1, scale=scale)
                else:
                    m[j,i] = ent.permutation_entropy(e_[j], m=embed, delay=tau)
            del e_
        return m

    def compute_psd_segm(raw, window=30):
        from mne.time_frequency import psd_welch
        from mne.io import RawArray

        def get_raw_array(data):
            ch_types  = ['eeg'] * chan_len
            info = mne.create_info(ch_names=raw.ch_names, sfreq=sfreq, ch_types=ch_types)
            raw_array = RawArray(data, info=info)
            return raw_array

        data = raw.get_data()
        sfreq = raw.info['sfreq']
        length_dp = len(raw.times)
        window_dp = int(window*sfreq)
        no_epochs = int(length_dp // window_dp)
        chan_len = len(raw.ch_names)
        store_psd = []
        for i in range(no_epochs):
            e_ = data[...,:window_dp]
            data = np.delete(data, np.s_[:window_dp], axis =1 )
            ra = get_raw_array(e_)
            psd, freqs = psd_welch(ra ,fmin=1,fmax=30)
            #psd = 10 * np.log10(psd) # log is done latter on, in wrap_psd.py
            store_psd.append(psd)
        #psd array of shape [freqs, channs, epochs]
        return freqs, np.asarray(store_psd).transpose(2,1,0)

    def encode(stag):
        stages_coding = {'N' : 1, 'R' : 2, 'W' : 3,'X' : 4, 'XW' : 5, 'WR' : 6, 'RW' : 7, 'XR' : 8, 'WN' : 9}
        stag['numeric'] = stag.replace(stages_coding, inplace=False).astype(float)
        return stag

    idfs = map_stag_with_raw(fnames, s, sufx='ref100')
    idfs = {i : v for i, v in idfs.items() if len(v) >= 1} # drop empty
    idfs = {i : v for i, v in idfs.items() if 'P' not in i} # drop Prechtls
    #write idfs df to excel
    #from write_data import mywriter
    #mywriter(idfs, sheet + '.xlsx')

    #select single subject
    #sbj = '211_2_S'
    #idfs = {k : v for k,v in idfs.items() if k == sbj}

    from config import paths
    for k, v in sorted(idfs.items()):
        #no overwriting!!!!!! comment out if overw. desired
        #
        #k_short = k.split('_S')[0]
        #p = paths(typ=setup, sbj=k_short) #path to a folder
        #if os.path.exists(p):
        #    continue
        #
        if k not in bad:
            print k
            raw, stag = load_raw_and_stag(k, v[0])
            raw, _ = order_channels(raw) #reorder channels, add zeros for missings (EMG usually)
            stag = encode(stag)
            #pe = compute_pe_segm(raw, embed=embed, tau=tau, mspe=False)
            freqs, psd = compute_psd_segm(raw, window=30)
            mysave(var = [stag, psd, freqs], typ=typ_name, sbj=k[:5])
            #mysave(var = [stag, pe], typ=typ_name, sbj=k[:5])
        elif k in bad:
            print 'Sbj dropped, see red annot. by H.L in excel file'
            continue
