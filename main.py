#!/usr/bin/env python
from joblib import Parallel, delayed
import math
### Custom libraries
from common.functions import IS_DEBUG, read_config, debug, fn_timer
from preprocessings.read import extract_checkins_per_user, extract_checkins_per_venue, extract_checkins_all
from methods.colocation import process_map, process_reduce, prepare_colocation

def init_begin_end(n_core, size, start=0, finish=-1):
  begin = []
  end = []
  n_chunks = 50
  iteration = n_core*n_chunks
  size_per_chunk = int(size / iteration)
  for i in range(iteration):
    if i == 0:
      begin.append(0)
    else:
      begin.append(i*size_per_chunk)
    if i == iteration - 1:
      end.append(size)
    else:
      end.append((i+1)*size_per_chunk)
  ### If the start and finish are different from default
  if start < 0:
    start = 0
  if finish > size:
    finish = size
  if start == 0 and finish == -1:
    pass
  else:
    if finish == -1:
      finish = size
    idx_start = -1
    idx_finish = -1
    for i in range(len(begin)):
      if begin[i] >= start:
        idx_start = i
        break
    for i in xrange(len(end)-1, -1, -1):
      if finish >= end[i]:
        idx_finish = i+1
        break
    begin = begin[idx_start:idx_finish]
    end = end[idx_start:idx_finish]
  assert len(begin) == len(end) ### Make sure the length of begin == length of end
  return begin, end

@fn_timer
def map_reduce_colocation(config, checkins, p, k, t_diff, s_diff):
  n_core = config['n_core']
  start = config['kwargs']['colocation']['start']
  finish = config['kwargs']['colocation']['finish']
  ### For the sake of parallelization
  begins, ends = init_begin_end(n_core, len(checkins), start=start, finish=finish)
  debug('Begins', begins)
  debug('Ends', ends)
  ### Generate colocation based on extracted checkins
  prepare_colocation(config, p, k, t_diff, s_diff, begins, ends)
  Parallel(n_jobs=n_core)(delayed(process_map)(checkins, config, begins[i-1], ends[i-1], p, k, t_diff, s_diff) for i in xrange(len(begins), 0, -1))
  process_reduce(config, p, k, t_diff, s_diff)
  debug('Finished map-reduce for [p%d, k%d, t%d, d%.3f]' % (p, k, t_diff, s_diff))

def run_colocation(config, run_by='user'):
  ### Read standardized data and perform preprocessing
  n_core = config['n_core']
  all_datasets = config['dataset']
  all_modes = config['mode']
  datasets = config['active_dataset']
  modes = config['active_mode']
  t_diffs = config['ts']
  s_diffs = config['ds']
  for dataset_name in datasets:
    p = all_datasets.index(dataset_name)
    for mode in modes:
      k = all_modes.index(mode)
      debug('Dataset', dataset_name, p, 'Mode', mode, k, '#Core', n_core)
      ### Extracting checkins
      if run_by == 'venue': ### If extracted by each venue (Simplified SIGMOD 2013 version)
        checkins = extract_checkins_per_venue(dataset_name, mode, config)
      elif run_by == 'checkin':
        checkins = extract_checkins_all(dataset_name, mode, config)
      else: ### Default is by each user
        checkins = extract_checkins_per_user(dataset_name, mode, config)
      for t_diff in t_diffs:
        for s_diff in s_diffs:
          map_reduce_colocation(config, checkins, p, k, t_diff, s_diff)

def main():
  debug('Started SCI+')
  ### Read config
  config = read_config()
  kwargs = config['kwargs']
  is_run_colocation = kwargs['colocation']['run']
  if is_run_colocation is not None and is_run_colocation is True:
    ### Co-location generation
    run_colocation(config)
  debug('Finished SCI+')

if __name__ == '__main__':
  main()