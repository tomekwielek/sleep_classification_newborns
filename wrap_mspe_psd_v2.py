'''
process  PSD values: load separately for t1 and t2,
get average psd for given sleep stage, pack into df,
ploting
'''
import os
import numpy as np
import pandas as pd
from config import myload, base_path, paths, chs_incl, subjects, bad_sbjs_1, bad_sbjs_2, chs_incl
from functional import (select_class_to_classif,  load_single_append)
from functional import select_class_to_classif, remove_20hz_artif
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.core.debugger import set_trace
import scipy.stats
import numpy as np, scipy.stats as st
import seaborn as sns
from random import shuffle
import random


path = 'H:\\BABY\\working\subjects'
fnames =  os.listdir(path)
fnames1 = [f for f in fnames if f.endswith('1')]
fnames2 = [f for f in fnames if f.endswith('2')] #filter folders

sel_idxs = [1,2,3]
select_single_channel = 'O2' #'O1' #'O2' #specify channel to select
k= 'all' # epochs to average
balance_sbjs_across_groups = False #if True sample 12 estimates from each group (e,g week2 NREM)

store_scores = dict()
store_pval = dict()

mspe1, mspe_stag1, mspe_names1, _ = load_single_append(path, fnames1, typ='mspet1m3')
mspe2, mspe_stag2, mspe_names2, _ = load_single_append(path, fnames2, typ='mspet1m3')
psd1, psd_stag1, psd_names1, freqs = load_single_append(path, fnames1, typ='psd')
psd2, psd_stag2, psd_names2, freqs = load_single_append(path, fnames2, typ='psd')

assert all([all(mspe_stag1[i] == psd_stag1[i]) for i in range(len(psd_stag1))])
assert all([all(mspe_stag2[i] == psd_stag2[i]) for i in range(len(psd_stag2))])
del (psd_stag1, psd_stag2)

mspe1, psd1, stag1, _ = remove_20hz_artif(mspe1, psd1, mspe_stag1, mspe_names1, freqs, bad_sbjs_1)
mspe2, psd2, stag2, _ = remove_20hz_artif(mspe2, psd2, mspe_stag2, mspe_names2, freqs, bad_sbjs_2)

# Relative power see: Xiao(2018)
rel_psd1 = [psd1[i] / np.abs(np.sum(psd1[i], 0)) for i in range(len(psd1))]
rel_psd1 = [ np.log10(rel_psd1[i]) for i in range(len(psd1)) ]
rel_psd2 = [psd2[i] / np.abs(np.sum(psd2[i], 0)) for i in range(len(psd2))]
rel_psd2 = [ np.log10(rel_psd2[i]) for i in range(len(psd2)) ]

#drop last  channesl (EOG, ECG) etc
rel_psd1 = [rel_psd1[i][:,:-5,:] for i in range(len(rel_psd1))]
rel_psd2 = [rel_psd2[i][:,:-5,:] for i in range(len(rel_psd2))]
mspe1 = [mspe1[i][:,:-5,:] for i in range(len(mspe1))]
mspe2 = [mspe2[i][:,:-5,:] for i in range(len(mspe2))]

mspe1, stag1, _ = select_class_to_classif(mspe1, stag1, sel_idxs=sel_idxs)
mspe2, stag2, _ = select_class_to_classif(mspe2, stag2, sel_idxs=sel_idxs)
rel_psd1, stag1, _ = select_class_to_classif(rel_psd1, stag1, sel_idxs=sel_idxs)
rel_psd2, stag2, _ = select_class_to_classif(rel_psd2, stag2, sel_idxs=sel_idxs)

def av_channels_epochs(data, stag, what_stag, names):
    '''
    Function agragates across epochs and/or channels
    '''
    #select data corr with given sleep stage s
    av_stag = [data[i][:,:, np.where(stag[i]['numeric'] == what_stag)] for i in range(len(data))]
    names_ss = [ names[i] for i in range(len(av_stag)) if av_stag[i].size != 0 ]
    if k != 'all': #average k number of epochs
        ep_i = [ av_stag[i].shape[3] for i in range(len(av_stag)) ] #count how many epochs we have for given ss
        #randmoly sample epochs
        ep_sample_i = [np.random.choice(ep_i[i], size=k, replace=False) if ep_i[i] > k  else [] if ep_i[i] == 0 else np.arange(ep_i[i]) for i in range(len(ep_i)) ]
        #average epochs using random index
        av_stag =[ np.where(len(ep_sample_i[i]) > 0 , np.median(av_stag[i][:,:,:,ep_sample_i[i]], 3), np.nan) for i in range(len(av_stag)) ]
    else: #average all epochs
        av_stag =[ np.where(av_stag[i].size != 0, np.nanmedian(av_stag[i], 3), np.full(av_stag[i].shape[:3], np.nan)) for i in range(len(av_stag))]

    #average or select channels
    if select_single_channel is not False:
        ch_idx = np.where(np.asarray(chs_incl)==select_single_channel)[0]
        av_stag = [np.squeeze(np.asarray(av_stag[i][:,ch_idx,:])) for i in range(len(av_stag))]
    else:
        av_stag = [np.squeeze(np.nanmedian(av_stag[i], 1)) for i in range(len(av_stag))]

    return av_stag, names_ss

def iterate_stages_getdict(data, stag, sel_idxs, names):

    mydict = {}
    freq_bins_len = data[0].shape[0]
    for s in sel_idxs:
        channels_aved, found_names = av_channels_epochs(data, stag, s, names)
        #drop arrays with nan
        channels_aved = [ channels_aved[i] for i in range(len(channels_aved)) if not np.isnan(channels_aved[i][0]) ]
        #sample 12, count(week2 NREM) = 12
        if balance_sbjs_across_groups:
            random.Random(123).shuffle(channels_aved)
            channels_aved = channels_aved[:12]
            found_names =  [[] for i in range(12)]
 #when balancing skip names
        mydict[str(s)] =(channels_aved, found_names)

    return mydict

# keys repr. ss and values av. psd e.g:
# mydict['1'][0] repr. list (all sbjs) with av. psd for ss. '1'

mydict1 = iterate_stages_getdict(rel_psd1, stag1, sel_idxs, psd_names1)
mydict1_mspe = iterate_stages_getdict(mspe1, stag1, sel_idxs, mspe_names1)

mydict2 = iterate_stages_getdict(rel_psd2, stag2, sel_idxs, psd_names2)
mydict2_mspe = iterate_stages_getdict(mspe2, stag2, sel_idxs, mspe_names2)

# wrap_together_df stacks averaged epochs across subjects, returned df.shape is
#  #N*len('1', '2', '2') x #freq_bins
def wrap_together_df(mydict):
    nrem = np.vstack(mydict['1'][0])
    rem = np.vstack(mydict['2'][0])
    wake = np.vstack(mydict['3'][0])
    def built_df(stag, data, names):
        df = pd.DataFrame(data, columns = range(data.shape[1]))
        df['stag'] = [stag] * data.shape[0]
        df['sbj_id'] = names
        return df
    dfs = []
    nrem_ns = mydict['1'][1]
    rem_ns = mydict['2'][1]
    wake_ns = mydict['3'][1]
    for s, d, n  in zip(['nrem', 'rem', 'wake'], [nrem, rem, wake], [nrem_ns, rem_ns, wake_ns]):
        df_ = built_df(s, d, n)
        dfs.append(df_)

    df = pd.concat(dfs, 0)
    return df
# pandas PSD
df1 = wrap_together_df(mydict1)
df1 = df1.dropna()
df1_long = pd.melt(df1, id_vars=['stag', 'sbj_id'])
df1['time'] = '2week'
df1_long['time'] = '2week'
df2 = wrap_together_df(mydict2)
df2 = df2.dropna()
df2_long = pd.melt(df2, id_vars=['stag', 'sbj_id'])
df2['time'] = '5week'
df2_long['time'] = '5week'
df_long = pd.concat([df1_long, df2_long])
df_wide_psd = pd.concat([df1, df2], sort=True)

#PSD PLOTTING
df = df_wide_psd.reset_index(drop=True)
df = df.dropna()
# returns confidence intervals of mean
def conf_int_mean(a, conf=0.95):
  mean, sem, m = np.mean(a), st.sem(a), st.t.ppf((1+conf)/2., len(a)-1)
  return mean - m*sem, mean + m*sem

def boot_conf_int_mean(a, conf=0.95):
    import pybootstrap as pb
    lower , upper = pb.bootstrap(a, confidence=conf, iterations=100, statistic=np.median, sample_size=1)
    #set_trace()
    return lower, upper

def get_IQR(a):
    from scipy.stats import iqr
    quant1 = np.percentile(a, 25.)
    quant2 = np.percentile(a, 75.)
    return quant1, quant2

def get_stats(group):
    return {'mean': group.mean()}
    #return {'min': group.min(), 'max': group.max(), 'count': group.count(), 'mean': group.mean()}

def get_overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))

'''
#testing, check grouping from  group by
g = df.groupby(['time', 'stag'])
result = [g_[1] for g_ in list(g)]
names = [g_[0] for g_ in list(g)]
av_res = list(result[0].mean(0))
'''


av = df.groupby(['time', 'stag']).aggregate(lambda x: np.mean(x)).reset_index()
'''
#get summary
df_long[df_long['variable']==0].groupby(['time', 'stag']).apply(get_stats).unstack()


df.groupby(['time', 'stag']).aggregate(lambda x: boot_conf_int_mean(x)).reset_index()
'''
#ci = df.groupby(['time', 'stag']).aggregate(lambda x: boot_conf_int_mean(x)).reset_index()
#ci = df.groupby(['time', 'stag']).aggregate(lambda x: get_IQR(x)).reset_index()
ci = df.groupby(['time', 'stag']).aggregate(lambda x: boot_conf_int_mean(x)).reset_index()
ci = ci.melt(id_vars=['time','stag'])
av = df.groupby(['time', 'stag']).aggregate(lambda x: np.median(x)).reset_index()
av = av.melt(id_vars=['time','stag'])
fig, axes = plt.subplots(1,3, sharey=True, figsize = (10,5))
ci_grouped = ci.groupby(['time', 'stag'])
dict_intervals = {}
colors = {'2week': 'black', '5week': 'red'}
for idx, s in enumerate(['nrem', 'rem', 'wake']):
    for t in ['2week', '5week']:
        myx = range(len(freqs))
        #interval = ci['value'].loc[(ci['stag']==s) & (ci['time']==t)]
        interval = ci['value'].loc[(ci['stag']==s) & (ci['time']==t)].values
        #smoth the intervals
        interval = np.asarray([list(interval[i]) for i in range(len(interval))])
        interval = zip(pd.Series(interval[:,0]).rolling(2).mean(), pd.Series(interval[:,1]).rolling(2).mean())

        #set_trace()
        dict_intervals[(t,s)] = interval
        axes[idx].fill_between(myx, y1=zip(*interval)[0], y2=zip(*interval)[1], alpha=0.5,
                                color=colors[t])
        this_av = av['value'].loc[(av['stag']==s) & (av['time']==t)]
        #smooth the av
        this_av = pd.Series(this_av).rolling(2).mean().values
        axes[idx].plot(myx, this_av, c='black', lw=2)
        axes[idx].set(xticks=myx, xticklabels=freqs.astype(int))
        old_ticks = axes[idx].get_xticks()
        axes[idx].set(xticks=old_ticks[::10], xticklabels=freqs.astype(int)[::10])
        axes[idx].set_title(s.upper(), fontsize=12)
        axes[idx].set_xlabel('Freqs [Hz]', fontsize=16)
        axes[idx].yaxis.set_ticklabels([])
        axes[0].set_ylabel('Log Relative Power', fontsize=20)
    #overlap =[ get_overlap(dict_intervals[('2week', s)].values[i],dict_intervals[('5week', s)].values[i])
    #            for i in range(len(freqs)) ]
    #overlap = np.array([ overlap[j] == 0 for j in range(len(freqs)) ], dtype=int)
    #mask overlapping intervals
    #y_values_masked = np.ma.masked_where(overlap == 0 , overlap)
    #axes[idx].plot(y_values_masked * -4, marker='o', c='black')
    if select_single_channel is not False:
        fig.suptitle(select_single_channel, size=18)

texts = ['week 2', 'week 5']
from matplotlib.lines import Line2D
custom_lines = [Line2D([0], [0], color=colors['2week'], lw=4, alpha=0.5, markersize=10),
                Line2D([0], [0], color=colors['5week'], lw=4, alpha=0.5)]

plt.legend(custom_lines,texts,bbox_to_anchor=(1.01, 1), loc=2, borderaxespad=0., ncol=1,
            prop={'size': 14}, title = '95% boot.ci. for median PSD').get_frame()
plt.show()

#MSPE PLOTTING
#pands MSPE
df1 = wrap_together_df(mydict1_mspe)
df1 = df1.dropna()
df1_long = pd.melt(df1, id_vars=['stag', 'sbj_id'])
df1['time'] = '2week'

df1_long['time'] = '2week'
df2 = wrap_together_df(mydict2_mspe)
df2 = df2.dropna()
df2_long = pd.melt(df2, id_vars=['stag', 'sbj_id'])
df2['time'] = '5week'
df2_long['time'] = '5week'
df_long = pd.concat([df1_long, df2_long])
df_wide_psd = pd.concat([df1, df2], sort=True)
#names without time suffiux
#df_long['sbj_id']=  [df_long['sbj_id'].iloc[i].split('_')[0] for i in range(len(df_long))]

df_long.to_csv('{}_mspe.csv'.format(select_single_channel))

def plot_stages_time_hued(df):
    fig, axes = plt.subplots(1,3, sharey=True, figsize = (10,5))
    for axi, s in enumerate(['nrem', 'rem', 'wake']):
        sns.pointplot(x='variable', y = 'value', hue='time', ci=95, \
                        data=df[df['stag']==s], ax = axes[axi], palette=colors, legend=True)
        axes[axi].set_title(s.upper())
        axes[axi].set_xlabel('Scale')
        axes[axi].set_xticklabels([1,2,3,4,5])
        axes[axi].set_ylabel('Permutation Entropy')
    fig.suptitle(channel, size=18)
    plt.show()
#plot_stages_time_hued(df_long)