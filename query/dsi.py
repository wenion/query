import json
import torch
from transformers import BertTokenizer
from ruamel.yaml import YAML

from query.models.ALBEF2 import ALBEF2
from query.models.image_encoder import interpolate_pos_embed

"""
class DSI:
    def __init__(self, settings):
        config = settings["config"]
        bert_base_uncased = settings["bert-base-uncased"]
        id_vocab = settings["id_vocab"]
        fine_tune_checkpoint_title = settings["fine_tune_checkpoint_title"]
        all_docid_knowledge = settings["all_docid_knowledge"]
        print(config, bert_base_uncased, id_vocab, fine_tune_checkpoint_title, all_docid_knowledge)
"""
class DSI:
    def __init__(self, settings):
        print("DSI ...")
        # self.config = yaml.load(open('./config.yaml', 'r'), Loader=yaml.Loader)
        yaml = YAML()
        # Load YAML data from a filewith 
        with open('./config.yaml', 'r') as yaml_file:
             self.config=yaml.load(yaml_file)
        #print("loaded config.yaml")     
        #self.device = torch.device('cuda')
        #print ("Setting the CUDA-enabled GPU for running tensors and models");
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        #print ("cuda enviroment is detected ..")
        self.tokenizer = BertTokenizer.from_pretrained('./bert-base-uncased', local_files_only=True)
        #print("trying loading the tokenizer from Hugging Face with the pretrained vocabulary from bert-base-uncased ...")
        #self.ids_tokenizer = Dec_Tokenizer.from_pretrained('./id_vocab.txt')
        self.ids_tokenizer = BertTokenizer.from_pretrained('./id_vocab.txt')
        #print("Loads vocabulary from a local file: './id_vocab.txt'")

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
        
        # with open('docid_title_pair.json', 'r') as file:
        with open('all_docid_knowledge.json', 'r') as file:
            self.id_title_dict = json.load(file)
            # print(self.id_title_dict)
        
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


def includeme(config):
    settings = config.registry.settings    
    dsi = DSI(settings, )
    config.registry["dsi"] = dsi
