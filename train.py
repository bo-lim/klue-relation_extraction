import os
import pandas as pd
import torch
import sklearn
import numpy as np
from sklearn.metrics import accuracy_score, recall_score, precision_score, f1_score
from transformers import AutoTokenizer, AutoConfig, AutoModelForSequenceClassification, \
    Trainer, TrainingArguments, RobertaConfig, RobertaTokenizer, RobertaForSequenceClassification, BertTokenizer, EarlyStoppingCallback
from load_data import *
from metric import *
from model import *

import wandb
import random
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit, train_test_split
from torch.utils.data import Subset, DataLoader
from custom_trainer import CustomTrainer

def train(RE_train_dataset, RE_dev_dataset, tokenizer, MODE="default", run_name="NoSetting", model = None):


  if model is None:
      AssertionError("MODEL을 설정해주세요!")
  # custom Trainer
  custom = False

  # hard-voting ensemble
  ensemble = True

  device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
  model.to(device)

  output_dir = './results' # TODO : output_dir 설정
  label_smoothing_factor = 0.0 # TODO : label_smoothing factor


  training_args = TrainingArguments(
      output_dir=output_dir,  # output directory
      save_total_limit=5,  # number of total save model.
      save_steps=200,  # model saving step.
      num_train_epochs=3,  # total number of training epochs
      learning_rate=2e-5,  # learning_rate
      per_device_train_batch_size=32,  # batch size per device during training
      per_device_eval_batch_size=32,  # batch size for evaluation
      warmup_steps=200,  # number of warmup steps for learning rate scheduler
      weight_decay=0.01,  # strength of weight decay
      logging_dir='./logs',  # directory for storing logs
      logging_steps=100,  # log saving step.
      evaluation_strategy='epoch',  # evaluation strategy to adopt during training
      # `no`: No evaluation during training.
      # `steps`: Evaluate every `eval_steps`.
      # `epoch`: Evaluate every end of epoch.
      eval_steps=500,  # evaluation step.
      metric_for_best_model="micro f1 score",
      load_best_model_at_end=True,
      report_to="wandb",
      # fp16=True,
      # fp16_opt_level="O1",
      label_smoothing_factor=label_smoothing_factor
  )

  if custom:
      trainer = CustomTrainer(
          model=model,  # the instantiated 🤗 Transformers model to be trained
          args=training_args,  # training arguments, defined above
          train_dataset=RE_train_dataset,  # training dataset
          eval_dataset=RE_dev_dataset,  # evaluation dataset
          compute_metrics=compute_metrics  # define metrics function
      )
  else:
      trainer = Trainer(
          model=model,  # the instantiated 🤗 Transformers model to be trained
          args=training_args,  # training arguments, defined above
          train_dataset=RE_train_dataset,  # training dataset
          eval_dataset=RE_dev_dataset,  # evaluation dataset
          compute_metrics=compute_metrics  # define metrics function
      )

  # Hard Voting Ensemble
  torch.cuda.empty_cache()
  if ensemble:
      train_val_split = StratifiedKFold(n_splits=3, shuffle=True, random_state=1004)
      idx = 0
      for train_idx, valid_idx in train_val_split.split(RE_train_dataset, RE_train_dataset.labels):
          idx += 1
          model_config = AutoConfig.from_pretrained(MODEL_NAME)
          model_config.num_labels = 30

          model_default = False
          model = get_model(MODEL_NAME=MODEL_NAME, tokenizer=tokenizer, model_default=model_default)

          # TODO : MODE가 "add_sptok"여야지만 num_added_sptoks가 설정됨
          model.to(device)
          train_subset = Subset(RE_train_dataset, train_idx)
          valid_subset = Subset(RE_train_dataset, valid_idx)

          if custom: # LDAM Loss 코드
              trainer = CustomTrainer(
                  loss_name='LDAMLoss',
                  model=model,  # the instantiated 🤗 Transformers model to be trained
                  args=training_args,  # training arguments, defined above
                  train_dataset=train_subset.dataset,  # training dataset
                  eval_dataset=valid_subset.dataset,  # evaluation dataset
                  compute_metrics=compute_metrics  # define metrics function
              )
          else:
              trainer = Trainer(
                  model=model,  # the instantiated 🤗 Transformers model to be trained
                  args=training_args,  # training arguments, defined above
                  train_dataset=train_subset,  # training dataset
                  eval_dataset=valid_subset,  # evaluation dataset
                  compute_metrics=compute_metrics  # define metrics function
              )
          # train model
          trainer.train()
          model.save_pretrained('./best_model/' + run_name + '_' + str(idx))
  else:
      trainer.train()
      model.save_pretrained('./best_model/' + run_name)

  torch.save(model, './best_model/model.pt')

def main():
  MODE = "default"
  run_name = "runname setting"

  train(MODE=MODE, run_name=run_name)

if __name__ == '__main__':
    main()