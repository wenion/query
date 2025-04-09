import json
import logging
import torch
from transformers import BertTokenizer
from ruamel.yaml import YAML

from query.models.ALBEF2 import ALBEF2
from query.models.image_encoder import interpolate_pos_embed

log = logging.getLogger(__name__)

"""
class DSI:
    def __init__(self, settings):
        print("DSI ...")
        config = settings["config"]
        bert_base_uncased = settings["bert-base-uncased"]
        id_vocab = settings["id_vocab"]
        fine_tune_checkpoint_title = settings["fine_tune_checkpoint_title"]
        all_docid_knowledge = settings["all_docid_knowledge"]
        print(config, bert_base_uncased, id_vocab, fine_tune_checkpoint_title, all_docid_knowledge)

    def gen_id(self, query, k=10):
        if query is None:
            raise Exception
        return [
            {
                'content': 'Description Towers of Hanoi (Part 2) Puzzle components include: disk will be represented by a positive int corresponding to the size of the disk. For example, if there are 4 disks, the disks (from smallest to the largest) will be represented by the integers 1, 2, 3 and 4, respectively. needle will be represented by a list of int corresponding to disks from bottom to top. For example, lists [4,3], [2,1] and [] represent the needles 0, 1 and 2 visualised below. state will be represented by a list of 3 lists corresponding to needles from left to right. For example, the list of 3 lists [[4,3],[2,1],[]] represents the state visualised above. Question 1 Write a function named start_state that inputs the number of disks n, and outputs the start state of the puzzle (i.e., all disks are on needle 0 where the disks are ordered from smallest to the largest from top to bottom). Expand Question 2 Write a function named aux that inputs two integers representing the needles, and outputs the other needle. Expand Question 3 Write a function named next_state that inputs i) the needle the disk moves from, ii) the needle the disk moves to and iii) the current state of the puzzle, and outputs the next state of the puzzle (i.e., as a result of moving the disk). Only the top disk is moved if there are multiple disks on a given needle. Expand Do NOT mutate the input list state. You do NOT need to use recursion to solve Questions 1-3. Description Use left and right arrow keys to adjust the split region size hanoi.py 1 /home/hanoi.py Spaces: 4 (Auto) Changes will not be saved. Reload Use up and down arrow keys to adjust the split region size Console Terminal Run',
                'title': 'FIT1045_FIT1053 S1 2023_Week 11 - Advanced Python_W11 Applied_Towers of Hanoi (Part 2).json',
                'summary': 'The summary is about a puzzle called Towers of Hanoi, which involves moving disks between needles. The puzzle components are represented by positive integers and lists. The questions involve creating functions to determine the start state of the puzzle, find the other needle given two needles, and determine the next state of the puzzle when a disk is moved. The input list should not be mutated and recursion is not required for solving the questions.',
                'url': 'https://edstem.org/au/courses/10682/lessons/31246/slides/248634',
                'repository': 'Ed'
            },
            {
                'content': 'Description Guess the secret number (iterative) In this activity we will combine a while loop and an if-elif-else, both seen in the pre-class activities. Question 1 (✓) Using a while loop, write a program that: Prompts "Enter guess: " and reads an integer input, Prints "Good guess!" if the number is 42, and terminates the program, Prints "Too high" if the number is greater than 42, and go back to step 1, Prints "Too low" if the number is smaller than 42, and go back to step 1. Hint Expand Question 2 (requires no further knowledge) Expand Sample input and output Description Use left and right arrow keys to adjust the split region size guess.py 1 2 3 4 5 #guess = int(input("Enter guess: ")) #print("Good guess!") #print("Too high") #print("Too low") /home/guess.py Spaces: 4 (Auto) All changes saved Use up and down arrow keys to adjust the split region size Console Terminal Run Mark',
                'title': 'FIT1045 OCT 2023 MUM_Week 02 - Conditionals and Iteration (while loops)_W2 Workshop_Guess the secret number (iterative).json',
                'summary': 'This activity involves writing a program that prompts the user to guess a secret number. If the guess is correct, the program terminates. If the guess is too high or too low, the program prompts the user to guess again. The program uses a while loop and an if-elif-else statement.',
                'url': 'https://edstem.org/au/courses/14043/lessons/44038/slides/300725',
                'repository': 'Ed'
            },
            {
                'content': '16 May - 22 May Week 11 - Cases of MML Week 11 text.L1 File Hidden from students text.L2 File Hidden from students Assignment 4 (due date Oct 21st) - Machine Translation File Hidden from students Clustering notes File 518.4KB PDF document Hidden from students Assignment 4 -- feature selection / clustering File 118.2KB PDF document Hidden from students Data for Assignment 4 Folder Hidden from students Simply MML Cases File 2.1MB PDF document Multivariable MML Cases File 1.5MB PDF document',
                'title': 'FIT4009 Advanced topics in intelligent systems S1 2016_section-12.json',
                'summary': 'In the given week, there were cases related to MML, assignment 4 on machine translation and feature selection/clustering, as well as notes and data for assignment 4. There were also documents on Simply MML and Multivariable MML cases.',
                'url': 'https://lms.monash.edu/course/view.php?id=28319#section-12',
                'repository': 'Moodle'
            },
        ]
"""
class DSI:
    def __init__(self, settings):
        yaml_config = settings["config"]
        bert_base_uncased_config = settings["bert-base-uncased"]
        id_vocab_config = settings["id_vocab"]
        fine_tune_checkpoint_title_config = settings["fine_tune_checkpoint_title"]
        all_docid_knowledge_config = settings["all_docid_knowledge"]

        log.info(f"DSI init settings: {str(settings)}")

        # self.config = yaml.load(open('./config.yaml', 'r'), Loader=yaml.Loader)
        yaml = YAML()
        # Load YAML data from a filewith 
        # with open('./config.yaml', 'r') as yaml_file:
        with open(yaml_config, 'r') as yaml_file:
             self.config=yaml.load(yaml_file)
        #print("loaded config.yaml")     
        #self.device = torch.device('cuda')
        #print ("Setting the CUDA-enabled GPU for running tensors and models");
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        #print ("cuda enviroment is detected ..")
        # self.tokenizer = BertTokenizer.from_pretrained('./data/bert-base-uncased', local_files_only=True)
        self.tokenizer = BertTokenizer.from_pretrained(bert_base_uncased_config, local_files_only=True)
        #print("trying loading the tokenizer from Hugging Face with the pretrained vocabulary from bert-base-uncased ...")
        # self.ids_tokenizer = BertTokenizer.from_pretrained('./id_vocab.txt')
        self.ids_tokenizer = BertTokenizer.from_pretrained(id_vocab_config)
        #print("Loads vocabulary from a local file: './id_vocab.txt'")

        log.info(f"DSI initial...")
        # model = ALBEF2(config=self.config, text_encoder='bert-base-uncased', text_decoder='bert-base-uncased', ids_tokenizer=self.ids_tokenizer, tokenizer=self.tokenizer)
        model = ALBEF2(config=self.config, text_encoder=bert_base_uncased_config, text_decoder=bert_base_uncased_config, ids_tokenizer=self.ids_tokenizer, tokenizer=self.tokenizer)
        self.model = model.to(self.device)   
        
        log.info(f'load checkpoint')
        checkpoint = torch.load(fine_tune_checkpoint_title_config, map_location='cpu')
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
        with open(all_docid_knowledge_config, 'r') as file:
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
                # print(self.id_title_dict[pred_id])
                pred_ids.append(self.id_title_dict[pred_id])

        return pred_ids#, response_ids


def includeme(config):
    settings = config.registry.settings    
    dsi = DSI(settings, )
    config.registry["dsi"] = dsi
