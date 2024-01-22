import argparse
import os
import re
from ruamel import yaml
import numpy as np
import random
import time
import datetime
import json
from pathlib import Path

import statistics
from collections import Counter
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.backends.cudnn as cudnn
import torch.distributed as dist
# from torch.utils.data import DataLoader

from models.ALBEF2 import ALBEF2
from models.image_encoder import interpolate_pos_embed
from models.tokenizer import BertTokenizer
from models.dec_tokenizer import Dec_Tokenizer


class DSI:
    def __init__(self):
        self.config = yaml.load(open('./config.yaml', 'r'), Loader=yaml.Loader)
        self.device = torch.device('cuda')
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.ids_tokenizer = Dec_Tokenizer.from_pretrained('./id_vocab.txt')
        
        print("DSI initial...")
        model = ALBEF2(config=self.config, text_encoder='bert-base-uncased', text_decoder='bert-base-uncased', ids_tokenizer=self.ids_tokenizer, tokenizer=self.tokenizer)
        self.model = model.to(self.device)   
        
        print('load checkpoint')
        checkpoint = torch.load('./fine_tune_checkpoint_title_58.pth', map_location='cpu') 
        state_dict = checkpoint['model']
        pos_embed_reshaped = interpolate_pos_embed(state_dict['visual_encoder.pos_embed'],model.visual_encoder)         
        state_dict['visual_encoder.pos_embed'] = pos_embed_reshaped
        msg = model.load_state_dict(state_dict,strict=False)  
        print(msg)  

        self.special_token_id = {}
        self.special_token_id['BOS'] = self.ids_tokenizer.convert_tokens_to_ids(self.config['bos'])
        self.special_token_id['EOS'] = self.ids_tokenizer.convert_tokens_to_ids(self.config['eos'])
        self.special_token_id['PAD'] = self.ids_tokenizer.convert_tokens_to_ids(self.config['pad'])
        self.retrieval_token_id = self.ids_tokenizer.convert_tokens_to_ids('retrieval')
        
        with open('docid_title_pair.json', 'r') as file:
            self.id_title_dict = json.load(file)
        
    def gen_id(self, query, k=10):
        pred_ids = []
        query_input = self.tokenizer(query, padding=True, truncation=True, max_length=30, return_tensors="pt").to(self.device)
        query_ids = torch.full((query_input.input_ids.size(0), 1), self.retrieval_token_id, dtype=torch.long).to(self.device)
        response_ids = self.model(summary=query_input, retrieval_id=query_ids, train=False, k=k, special_token=self.special_token_id)     
        
        for output in response_ids:
            pred_id = self.ids_tokenizer.decode(output, skip_special_tokens=True)
            pred_id = pred_id.split()
            pred_id = " ".join(pred_id[1:]) 

            if pred_id in self.id_title_dict.keys():
                print(self.id_title_dict[pred_id])
                pred_ids.append(self.id_title_dict[pred_id])

        return pred_ids#, response_ids
        
# def gen_id(model, tokenizer, ids_tokenizer, device, config, k=10):
#     model.eval()  
    
#     # metric_logger = utils.MetricLogger(delimiter="  ")
#     header = 'Generate: '
#     print_freq = 50
#     index_list = []
#     contents_list = []
    
#     bos_token_id = ids_tokenizer.convert_tokens_to_ids(config['bos'])
#     eos_token_id = ids_tokenizer.convert_tokens_to_ids(config['eos'])
#     pad_token_id = ids_tokenizer.convert_tokens_to_ids(config['pad'])
#     retrieval_token_id = ids_tokenizer.convert_tokens_to_ids('retrieval')
#     special_token_id = {}
#     special_token_id['BOS'] = bos_token_id
#     special_token_id['EOS'] = eos_token_id
#     special_token_id['PAD'] = pad_token_id
    
#     query = "update moodle"
    
#     query_input = tokenizer(query, padding=True, truncation=True, max_length=30, return_tensors="pt").to(device)
#     query_ids = torch.full((query_input.input_ids.size(0), 1), retrieval_token_id, dtype=torch.long).to(device)
#     response_ids = model(summary=query_input, retrieval_id=query_ids, train=False, k=k, special_token=special_token_id)
            
#     pred_ids = []
    
#     with open('docid_title_pair.json', 'r') as file:
#         data = json.load(file)
        
#     for output in response_ids:
#         pred_id = ids_tokenizer.decode(output, skip_special_tokens=True)
#         pred_id = pred_id.split()
#         pred_id = " ".join(pred_id[1:]) 
#         # pred_ids.append(pred_id)
        
#         if pred_id in data.keys():
#             print(data[pred_id])
#             pred_ids.append(data[pred_id])
    
#     return pred_ids#, response_ids


 
if __name__ == '__main__':
    dsi_model = DSI()
    query = "What are the key factors to consider when designing a PowerPoint presentation layout?"
    result = dsi_model.gen_id(query)import argparse
