# -*- coding: utf-8 -*-
"""train.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1TcyKwj-COwczssy8Q_xIPnYLymQyQors
"""

import os
import shutil

import random
import numpy as np
import time
import cv2
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision.transforms import Compose, ToTensor
from torch.utils.data import Dataset
import torchvision.transforms as transforms
from torch.cuda.amp import autocast, GradScaler
from torch.optim.lr_scheduler import CosineAnnealingLR
from torchvision.transforms import CenterCrop, Resize
from PIL import Image
from model import Restormer
import warnings
warnings.filterwarnings(action='ignore')

CFG = {
    'IMG_SIZE':224,
    'EPOCHS':5,
    'LEARNING_RATE':2e-4,
    'BATCH_SIZE':4,
    'SEED':42
}

def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

seed_everything(CFG['SEED']) # Seed 고정

class CustomDataset(Dataset):
    def __init__(self, clean_image_paths, noisy_image_paths, transform=None):
        self.clean_image_paths = [os.path.join(clean_image_paths, x) for x in os.listdir(clean_image_paths)]
        self.noisy_image_paths = [os.path.join(noisy_image_paths, x) for x in os.listdir(noisy_image_paths)]
        self.transform = transform
        self.center_crop = CenterCrop(1080)
        self.resize = Resize((CFG['IMG_SIZE'], CFG['IMG_SIZE']))

        # Create a list of (noisy, clean) pairs
        self.noisy_clean_pairs = self._create_noisy_clean_pairs()

    def _create_noisy_clean_pairs(self):
        clean_to_noisy = {}
        for clean_path in self.clean_image_paths:
            clean_id = '_'.join(os.path.basename(clean_path).split('_')[:-1])
            clean_to_noisy[clean_id] = clean_path

        noisy_clean_pairs = []
        for noisy_path in self.noisy_image_paths:
            noisy_id = '_'.join(os.path.basename(noisy_path).split('_')[:-1])
            if noisy_id in clean_to_noisy:
                clean_path = clean_to_noisy[noisy_id]
                noisy_clean_pairs.append((noisy_path, clean_path))
            else:
                pass

        return noisy_clean_pairs

    def __len__(self):
        return len(self.noisy_clean_pairs)

    def __getitem__(self, index):
        noisy_image_path, clean_image_path = self.noisy_clean_pairs[index]

        noisy_image = Image.open(noisy_image_path).convert("RGB")
        clean_image = Image.open(clean_image_path).convert("RGB")

        # Central Crop and Resize
        noisy_image = self.center_crop(noisy_image)
        clean_image = self.center_crop(clean_image)
        noisy_image = self.resize(noisy_image)
        clean_image = self.resize(clean_image)

        if self.transform:
            noisy_image = self.transform(noisy_image)
            clean_image = self.transform(clean_image)

        return noisy_image, clean_image

import time
import numpy as np
import os
import torch
import torch.optim as optim
import torchvision.transforms as transforms
import cv2
from torch.utils.data import DataLoader
from torch.cuda.amp import GradScaler, autocast
from torch.optim.lr_scheduler import CosineAnnealingLR

# 시작 시간 기록
start_time = time.time()

class EarlyStopping:
    def __init__(self, patience=2, min_delta=0):
        self.patience = patience  # 성능 개선을 기다리는 횟수
        self.min_delta = min_delta  # 개선 정도
        self.best_loss = np.Inf  # 가장 낮은 validation loss
        self.counter = 0  # 개선되지 않은 epoch 수
        self.early_stop = False  # early stopping 신호

    def __call__(self, val_loss, model, model_path='best_modelll.pth'):
        # validation loss가 개선된 경우
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
            torch.save(model.state_dict(), model_path)  # 모델 저장
        else:
            # 개선되지 않은 경우
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True  # 학습 중단 신호 설정

def weights_init(m):
    if isinstance(m, nn.Conv2d):
        nn.init.kaiming_uniform_(m.weight.data, mode='fan_in', nonlinearity='relu')

def load_img(filepath):
    img = cv2.imread(filepath)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

# 데이터셋 경로
noisy_image_paths = '/content/drive/MyDrive/Training/noisy'
clean_image_paths = '/content/drive/MyDrive/Training/clean'
val_noisy_image_paths = '/content/drive/MyDrive/Validation/noisy'  # 검증 데이터셋 경로
val_clean_image_paths = '/content/drive/MyDrive/Validation/clean'  # 검증 데이터셋 경로

# 데이터셋 로드 및 전처리
train_transform = transforms.Compose([
    transforms.RandomApply([transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0))], p=0.3),  # 30% 확률로 가우시안 블러
    transforms.ToTensor(),  # 텐서로 변환
    transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])  # 정규화
])

val_transform = transforms.Compose([
    transforms.ToTensor(),  # 텐서로 변환
    transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])  # 정규화
])

# 커스텀 데이터셋 인스턴스 생성
train_dataset = CustomDataset(clean_image_paths, noisy_image_paths, transform=train_transform)
val_dataset = CustomDataset(val_clean_image_paths, val_noisy_image_paths, transform=val_transform)  # 검증 데이터셋 생성

# 데이터 로더 설정
num_cores = os.cpu_count()
train_loader = DataLoader(train_dataset, batch_size=CFG['BATCH_SIZE'], num_workers=int(num_cores/2), shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=CFG['BATCH_SIZE'], num_workers=int(num_cores/2), shuffle=False)  # 검증 데이터 로더

# GPU 사용 여부 확인
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Restormer 모델 인스턴스 생성 및 GPU로 이동
model = Restormer().to(device)

# 손실 함수와 최적화 알고리즘 설정
optimizer = optim.AdamW(model.parameters(), lr=CFG['LEARNING_RATE'], weight_decay=1e-4)
criterion = nn.L1Loss()
scaler = GradScaler()
scheduler = CosineAnnealingLR(optimizer, T_max=CFG['EPOCHS'])

# 모델의 파라미터 수 계산
total_parameters = count_parameters(model)
print("Total Parameters:", total_parameters)

# EarlyStopping 인스턴스 생성
early_stopping = EarlyStopping(patience=2, min_delta=0.001)

# 모델 학습
model.train()
model.load_state_dict(torch.load("/content/best_Restormerrrrrrr.pth"), strict=False)
best_loss = 1000

for epoch in range(CFG['EPOCHS']):
    model.train()
    epoch_start_time = time.time()
    mse_running_loss = 0.0

    # 훈련 단계
    for noisy_images, clean_images in train_loader:
        noisy_images = noisy_images.to(device)
        clean_images = clean_images.to(device)

        optimizer.zero_grad()

        with autocast():
            outputs = model(noisy_images)
            mse_loss = criterion(outputs, clean_images)

        scaler.scale(mse_loss).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()
        scheduler.step()

        mse_running_loss += mse_loss.item() * noisy_images.size(0)

    current_lr = scheduler.get_last_lr()[0]
    epoch_end_time = time.time()
    epoch_time = epoch_end_time - epoch_start_time
    minutes = int(epoch_time // 60)
    seconds = int(epoch_time % 60)
    hours = int(minutes // 60)
    minutes = int(minutes % 60)

    mse_epoch_loss = mse_running_loss / len(train_dataset)
    print(f"Epoch {epoch+1}/{CFG['EPOCHS']}, MSE Loss: {mse_epoch_loss:.4f}, Lr: {current_lr:.8f}")
    print(f"1epoch 훈련 소요 시간: {hours}시간 {minutes}분 {seconds}초")

    # 검증 단계
    model.eval()
    mse_val_loss = 0.0
    with torch.no_grad():
        for val_noisy_images, val_clean_images in val_loader:
            val_noisy_images = val_noisy_images.to(device)
            val_clean_images = val_clean_images.to(device)

            with autocast():
                val_outputs = model(val_noisy_images)
                val_loss = criterion(val_outputs, val_clean_images)

            mse_val_loss += val_loss.item() * val_noisy_images.size(0)

    mse_val_loss /= len(val_dataset)
    print(f"Validation MSE Loss: {mse_val_loss:.4f}")

    # Early Stopping 체크
    early_stopping(mse_val_loss, model)

    if early_stopping.early_stop:
        print("Early stopping triggered. Training stopped.")
        break

# 종료 시간 기록
end_time = time.time()

# 소요 시간 계산
training_time = end_time - start_time
minutes = int(training_time // 60)
seconds = int(training_time % 60)
hours = int(minutes // 60)
minutes = int(minutes % 60)

# 결과 출력
print(f"훈련 소요 시간: {hours}시간 {minutes}분 {seconds}초")