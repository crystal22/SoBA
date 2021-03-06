#!/usr/bin/env python
from joblib import Parallel, delayed
import math
import gc
import sys
### Custom libraries
from common.functions import IS_DEBUG, read_config, debug, fn_timer, \
  init_begin_end, make_sure_path_exists, remove_file_if_exists, is_file_exists
from preprocessings.read import extract_checkins_per_user, extract_checkins_per_venue, \
  extract_checkins_all
from methods.colocation import process_map, process_reduce, prepare_colocation, \
  generate_colocation_single
from methods.sci import extract_popularity, extract_colocation_features
from methods.evaluation import sci_evaluation, pgt_evaluation
from methods.pgt import extract_personal_pgt, extract_global_pgt, extract_pgt

@fn_timer
def map_reduce_colocation(config, checkins, grouped, p, k, t_diff, s_diff):
  kwargs = config['kwargs']
  n_core = kwargs['n_core']
  start = kwargs['colocation']['start']
  finish = kwargs['colocation']['finish']
  order = kwargs['colocation']['order']
  ### For the sake of parallelization
  begins, ends = init_begin_end(n_core, len(grouped), start=start, finish=finish)
  debug('Begins', begins)
  debug('Ends', ends)
  ### Generate colocation based on extracted checkins
  prepare_colocation(config, p, k, t_diff, s_diff, begins, ends)
  ### Start from bottom
  if order == 'ascending':
    Parallel(n_jobs=n_core)(delayed(process_map)(checkins, grouped, config, begins[i], ends[i], \
      p, k, t_diff, s_diff) for i in range(len(begins)))
  else:
    Parallel(n_jobs=n_core)(delayed(process_map)(checkins, grouped, config, begins[i-1], ends[i-1], \
      p, k, t_diff, s_diff) for i in xrange(len(begins), 0, -1))
  process_reduce(config, p, k, t_diff, s_diff)
  debug('Finished map-reduce for [p%d, k%d, t%d, d%.3f]' % (p, k, t_diff, s_diff))

@fn_timer
def map_reduce_colocation_kdtree(checkins, config, p, k, t_diff, s_diff):
  generate_colocation_single(checkins, config, p, k, t_diff, s_diff)
  process_reduce(config, p, k, t_diff, s_diff)

def extract_checkins(config, dataset_name, mode, run_by):
  ### Extracting checkins
  if run_by == 'location': ### If extracted by each venue (Simplified SIGMOD 2013 version)
    checkins, grouped = extract_checkins_per_venue(dataset_name, mode, config)
  elif run_by == 'checkin': ### Map-reduce fashion but per check-in
    checkins, grouped = extract_checkins_all(dataset_name, mode, config)
  else: ### Default is by each user
    checkins, grouped = extract_checkins_per_user(dataset_name, mode, config)
  return checkins, grouped

def run_colocation(config, run_by):
  ### Read standardized data and perform preprocessing
  kwargs = config['kwargs']
  all_datasets = config['dataset']
  all_modes = config['mode']
  n_core = kwargs['n_core']
  datasets = kwargs['active_dataset']
  modes = kwargs['active_mode']
  t_diffs = kwargs['ts']
  s_diffs = kwargs['ds']
  skip_tolerance = kwargs['colocation']['early_stop']
  debug('early_stop', skip_tolerance)  
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Run co-location on Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      ### Extracting checkins
      checkins, grouped = extract_checkins(config, dataset_name, mode, run_by)
      for t_diff in t_diffs:
        for s_diff in s_diffs:
          if run_by == 'user' or run_by == 'location':
            map_reduce_colocation(config, checkins, grouped, p, k, t_diff, s_diff)
          else:
            map_reduce_colocation_kdtree(checkins, config, p, k, t_diff, s_diff)
      checkins.drop(checkins.index, inplace=True)
      del checkins
      if grouped is not None:
        grouped.drop(grouped.index, inplace=True)
        del grouped
      gc.collect()

def run_sci(config):
  ### Read standardized data and perform preprocessing
  kwargs = config['kwargs']
  n_core = kwargs['n_core']
  all_datasets = config['dataset']
  all_modes = config['mode']
  datasets = kwargs['active_dataset']
  modes = kwargs['active_mode']
  t_diffs = kwargs['ts']
  s_diffs = kwargs['ds']
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Run SCI on Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      ### Extracting checkins
      checkins, _ = extract_checkins(config, dataset_name, mode, 'user')
      stat_lp = extract_popularity(checkins, config, p, k)
      Parallel(n_jobs=n_core)(delayed(extract_colocation_features)(stat_lp, config, \
        p, k, t_diff, s_diff) for t_diff in t_diffs for s_diff in s_diffs)
      checkins.drop(checkins.index, inplace=True)
      del checkins
      gc.collect()

def run_sci_eval(config):
  kwargs = config['kwargs']
  n_core = kwargs['n_core']
  all_datasets = config['dataset']
  all_modes = config['mode']
  datasets = kwargs['active_dataset']
  modes = kwargs['active_mode']
  t_diffs = kwargs['ts']
  s_diffs = kwargs['ds']
  report_directory = config['directory']['report']
  make_sure_path_exists(report_directory)
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Run SCI Evaluation on Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      ### Creating the report file
      result_filename = '/'.join([report_directory, 'SCI_result_p{}_k{}.csv'.format(p,k)])
      remove_file_if_exists(result_filename)
      with open(result_filename, 'ab') as fw:
          fw.write('p,k,t,d,auc,precision,recall,f1,#friends,#data,feature_set,preprocessing\n')
      for t_diff in t_diffs:
        for s_diff in s_diffs:
          sci_evaluation(config, p, k, t_diff, s_diff)
          gc.collect()

def run_pgt(config):
  kwargs = config['kwargs']
  n_core = kwargs['n_core']
  all_datasets = config['dataset']
  all_modes = config['mode']
  datasets = kwargs['active_dataset']
  modes = kwargs['active_mode']
  t_diffs = kwargs['ts']
  s_diffs = kwargs['ds']
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Run PGT Extraction on Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      if kwargs['pgt']['personal']['run']:
        extract_personal_pgt(config, p, k)
      if kwargs['pgt']['global']['run']:
        extract_global_pgt(config, p, k)
      if config['kwargs']['pgt']['extract_pgt']['temporal'] is False:
        Parallel(n_jobs=n_core)(delayed(extract_pgt)(config, p, k, t_diff, s_diff) \
          for t_diff in t_diffs for s_diff in s_diffs)
        gc.collect()
      else:
        for t_diff in t_diffs:
          for s_diff in s_diffs:
            extract_pgt(config, p, k, t_diff, s_diff)
            gc.collect()

def run_pgt_evaluation(config):
  kwargs = config['kwargs']
  n_core = kwargs['n_core']
  all_datasets = config['dataset']
  all_modes = config['mode']
  datasets = kwargs['active_dataset']
  modes = kwargs['active_mode']
  t_diffs = kwargs['ts']
  s_diffs = kwargs['ds']
  report_directory = config['directory']['report']
  make_sure_path_exists(report_directory)
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Run PGT Evaluation on Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      ### Creating the report file
      result_filename = '/'.join([report_directory, 'PGT_result_p{}_k{}.csv'.format(p,k)])
      remove_file_if_exists(result_filename)
      with open(result_filename, 'ab') as fw:
          fw.write('p,k,t,d,auc,precision,recall,f1,#friends,#data,feature_set,preprocessing\n')
      for t_diff in t_diffs:
        for s_diff in s_diffs:
          pgt_evaluation(config, p, k, t_diff, s_diff)
          gc.collect()

def main(config_name='config.json'):
  ### Started the program
  debug('Started SCI+', config_name)
  ### Read config
  config = read_config(config_name)
  kwargs = config['kwargs']
  ### Co-location
  is_run = kwargs['colocation']['run']
  run_by = kwargs['colocation']['run_by']
  if is_run is not None and is_run is True:
    ### Co-location generation
    run_colocation(config, run_by)
  ### SCI
  is_run = kwargs['sci']['run']
  if is_run is not None and is_run is True:
    run_sci(config)
  ### SCI Evaluation
  is_run = kwargs['sci_eval']['run']
  if is_run is not None and is_run is True:
    run_sci_eval(config)
  ### PGT
  is_run = kwargs['pgt']['run']
  if is_run is not None and is_run is True:
    run_pgt(config)
  ### PGT Evaluation
  is_run = kwargs['pgt_eval']['run']
  if is_run is not None and is_run is True:
    run_pgt_evaluation(config)
  ### Finished the program
  debug('Finished SCI+')

if __name__ == '__main__':
  n_args = len(sys.argv)
  config_name = 'config.json'
  if n_args > 1:
    config_name = sys.argv[1]
  if is_file_exists(config_name) is False:
    config_name = 'config.json'
  main(config_name=config_name)