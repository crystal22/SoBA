#!/usr/bin/env python
"""
Please run this code under the root directory using the command 'python preprocessing/read.py'
"""
### General library
import numpy as np
import pandas as pd
### Utility library
import pickle
import sys
import os.path
### Setup Directories for local library
PWD = os.getcwd()
sys.path.append(PWD)
### Local library
from common.functions import IS_DEBUG, debug, fn_timer, make_sure_path_exists, is_file_exists, read_config
from common.visual import gmplot
from methods.colocation import generate_colocation

RAW_CHECKIN_FILE = 'checkin.csv'

### Global
config_file = 'config.json'
final_column = ['user', 'timestamp', 'latitude', 'longitude', 'location']

"""
Generate three standardized compressed csv files which consist of all, weekend, and weekday data
"""
@fn_timer
def generate_results(root, dataset, df):
  ### Standardized
  checkin_all = 'checkin_all.csv.gz'
  checkin_weekday = 'checkin_weekday.csv.gz'
  checkin_weekend = 'checkin_weekend.csv.gz'
  ### Writing results to files
  df.to_csv('/'.join([root, dataset, checkin_all]), header=True, index=False, compression ='gzip')
  df_weekday = df[df.index.dayofweek < 5]
  df_weekday.to_csv('/'.join([root, dataset, checkin_weekday]), header=True, index=False, compression ='gzip')
  df_weekend = df[df.index.dayofweek >= 5]
  df_weekend.to_csv('/'.join([root, dataset, checkin_weekend]), header=True, index=False, compression ='gzip')

"""
Reading the foursquare checkin dataset
"""
@fn_timer
def read_foursquare2012_checkin(root, write=True):
  dataset = 'foursquare'
  debug('Read Checkin %s' %dataset)
  df = pd.read_csv('/'.join([root, dataset, RAW_CHECKIN_FILE]), parse_dates=['time'])
  debug(df.describe(include='all'))
  debug(df.head())
  ### Create a UNIX timestamp column from the datetime format
  df['timestamp'] = df['time'].values.astype(np.int64) // 10 ** 9
  ### Set the datetime as the index
  df = df.set_index('time')
  ### Reordering columns
  df = df[final_column]
  ### Error checking
  # odd = df.loc[df.longitude>-80, ['longitude', 'latitude']]
  ### Writing results to files
  if write is True:
    generate_results(root, dataset, df)

"""
Reading the checkin dataset from SNAP Stanford
dataset = 'gowalla' or 'brightkite'
"""
@fn_timer
def read_snap_stanford_checkin(root, dataset='gowalla', write=True):
  debug('Read SNAP Stanford Checkin %s' %dataset)
  df = pd.read_csv('/'.join([root, dataset, RAW_CHECKIN_FILE]), header=None, names=['user','timestamp','latitude','longitude','location'])
  debug(df.describe(include='all'))
  debug(df.head())
  ### Create a datetime column as the index
  df['time'] = pd.to_datetime(df['timestamp'], unit='s')
  df = df.set_index('time')
  debug(df.head())
  ### Reordering columns
  df = df[final_column]
  ### Writing results to files
  if write is True:
    generate_results(root, dataset, df)

"""
Read the standardized data
"""
def read_processed(root, dataset='gowalla', mode='all', id='user'):
  filename = 'checkin_{}.csv.gz'.format(mode)
  df = pd.read_csv('/'.join([root, dataset, filename]), names=final_column, header=0)
  df['u_count'] = df.groupby('user')['user'].transform('count')
  df['v_count'] = df.groupby('location')['location'].transform('count')
  ### Apply filtering
  ### User count > 10 and location visit > 2 (otherwise there is no co-location)
  df = df[(df['u_count'] > 10) & (df['v_count'] > 1)]
  df.drop(['u_count', 'v_count'], axis=1, inplace=True)
  ### Adding spatiotemporal information from dataframe
  if id == 'checkin':
    grouped = None
  else:
    aggregations = {
      'timestamp' : ['mean', 'min', 'max'],
      'latitude'  : ['mean', 'min', 'max'],
      'longitude' : ['mean', 'min', 'max']
    }
    grouped = df.groupby([id]).agg(aggregations)
    grouped.columns = grouped.columns.droplevel(level=0)
    grouped.reset_index(inplace=True)
    grouped.rename(columns={"timestamp_mean": "t_avg", "timestamp_min": "t_min", "timestamp_max":"t_max",
        "latitude_mean": "lat_avg", "latitude_min":"lat_min", "latitude_max":"lat_max", 
        "longitude_mean": "lon_avg", "longitude_min":"lon_min", "longitude_max":"lon_max"
        }, inplace=True)
    grouped.sort_values(by=['t_avg', 'lat_avg', 'lon_avg'], inplace=True)
  return df, grouped

def preprocess_data(root):
  write = False
  read_foursquare2012_checkin(root, write)
  read_snap_stanford_checkin(root, 'brightkite', write)
  read_snap_stanford_checkin(root, 'gowalla', write)

def visualize_data(df):
  test_limit = 100
  temp = df[0:test_limit]  ### For testing purpose --> to speed-up and understand the data
  gmplot(temp)

@fn_timer
def extract_checkins(dataset_name, mode, config, id='user'):
  debug('Processing %s [%s] for each %s' % (dataset_name, mode, id))
  dataset_root = config['directory']['dataset']
  df, grouped = read_processed(dataset_root, dataset_name, mode, id)
  debug('#checkins', len(df))
  return df, grouped

"""
Extract all the checkins and group them on each user
Input:
- dataset_name (foursquare, gowalla, brightkite)
- mode (all, weekday, weekend)
- config: config.json filename
Output:
- Single dataframe consists of all checkins
- Grouped dataframe based on the user
"""
def extract_checkins_per_user(dataset_name, mode, config):
  df, grouped = extract_checkins(dataset_name, mode, config, 'user')
  return df, grouped

"""
Extract all the checkins and group them on each user
Input:
- dataset_name (foursquare, gowalla, brightkite)
- mode (all, weekday, weekend)
- config: config.json filename
Output:
- Single dataframe consists of all checkins
- Grouped dataframe based on the venue
"""
def extract_checkins_per_venue(dataset_name, mode, config):
  df, grouped = extract_checkins(dataset_name, mode, config, 'location')
  return df, grouped

"""
Extract all the checkins and group them on each user
Input:
- dataset_name (foursquare, gowalla, brightkite)
- mode (all, weekday, weekend)
- config: config.json filename
Output:
- Single dataframe consists of all checkins
- None
"""
def extract_checkins_all(dataset_name, mode, config):
  df, grouped = extract_checkins(dataset_name, mode, config, 'checkin')
  return df, grouped

def extract_friendships(dataset_name, config):
  dataset_root = config['directory']['dataset']
  friendship_name = '/'.join([dataset_root, dataset_name, 'friend.csv'])
  colocation_dtypes = {
        'user1':np.int64,'user2':np.int64
    }
  friend_df = pd.read_csv(friendship_name, dtype=colocation_dtypes)
  return friend_df

"""
Retrieving the check-ins of user 'uid'
"""
def checkin_of_user(df, uid):
  return df.loc[df[id] == uid]

@fn_timer
def main():
  ### Read config
  config = read_config()
  kwargs = config['kwargs']

  ### Read original data and generate standardized data
  if kwargs['preprocessing']['read_original'] is True:
    dataset_root = config['directory']['dataset']
    preprocess_data(dataset_root)

if __name__ == '__main__':
  main()