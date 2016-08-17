import os
from pympler import asizeof

def show_object_size(obj, name):
    size = asizeof.asizeof(obj)
    print('Size of {0} is : {1:,} Bytes'.format(name, size))

def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        pass

def write_to_file(filename, text, append=True):
    if append:
        mode = 'a'
    else:
        mode = 'w'
    with open(filename, mode) as fw:
        fw.write(str(text) + '\n')
    pass

def write_to_file_buffered(filename, text_list, append=True):
    buffer_size = 10000
    counter = 0
    temp_str = ""
    for text in text_list:
        if counter < buffer_size:
            temp_str = temp_str + text + '\n'
        else:
            write_to_file(filename, temp_str, append)
            temp_str = ""
            counter = 0
        counter += 1
    # Write remaining text
    if temp_str != "":
        write_to_file(filename, temp_str, append)