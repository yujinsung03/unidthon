# -*- coding: utf-8 -*-
"""prerprocess.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1TcyKwj-COwczssy8Q_xIPnYLymQyQors
"""

import os
import shutil

def Preprocess(base_dir):
     clean_dir = os.path.join(base_dir, 'clean')
     noisy_dir = os.path.join(base_dir, 'noisy')

     os.makedirs(clean_dir, exist_ok=True)
     os.makedirs(noisy_dir, exist_ok=True)


     source_dirs = []
     for root, dirs, files in os.walk(base_dir):
         for dir_name in dirs:
             if 'GT' in dir_name:
                 source_dirs.append(os.path.join(root, dir_name))

     if not source_dirs:
         raise ValueError("No directory containing 'GT' found")

     for source_dir in source_dirs:
         for filename in os.listdir(source_dir):
             if filename.endswith('.jpg'):
                 shutil.move(os.path.join(source_dir, filename), os.path.join(clean_dir, filename))

     for root, dirs, files in os.walk(base_dir):
         for dir_name in dirs:
             if dir_name not in ['clean', 'noisy'] and 'GT' not in dir_name:
                 current_dir = os.path.join(root, dir_name)
                 for filename in os.listdir(current_dir):
                     if filename.endswith('.jpg'):
                         shutil.move(os.path.join(current_dir, filename), os.path.join(noisy_dir, filename))


     for root, dirs, files in os.walk(base_dir, topdown=False):
         for dir_name in dirs:
             dir_path = os.path.join(root, dir_name)
             if dir_name not in ['clean', 'noisy']:
                 shutil.rmtree(dir_path)

     print('preprocessing done')

data_dir = '/content/drive/MyDrive'
training_base_dir = os.path.join(data_dir, 'Training')
validation_base_dir = os.path.join(data_dir, 'Validation')

Preprocess(training_base_dir)
Preprocess(validation_base_dir)