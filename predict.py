from model.model import BaseQuestioner, ModelWrapper, QuestionerWithAnswer, QuestionerWithCaption, TextSampler, TopKSampler, BeamSampler, TwoStageSampler
from data.dataset import Tokenizer, build_dataset, CaptionProcessor, build_cc3m_dataset, CC3MDataset
from torch.utils.data import DataLoader
from utils import ToCuda
import torch
import json
from torch_lib.util import Count
import time


# w/o distributed running
def main():
    
    class QuestionIdGen:
        q_id = Count()
    
    q_id_gen = QuestionIdGen()
    
    with torch.no_grad():
        # with open('images.json') as f:
        #     all_images = json.load(f)
        # tokenizer
        tokenizer = Tokenizer()
        # build and load model
        model = BaseQuestioner(tokenizer, QuestionerWithCaption(), auto_regressive=True)
        # model = BaseQuestioner(tokenizer, QuestionerWithAnswer(), auto_regressive=True)
        model = ModelWrapper(model)
        # checkpoint = torch.load('./log/test/checkpoint/checkpoint.pt', map_location='cpu')
        checkpoint = torch.load('./log/main2/checkpoint/checkpoint_10.pth', map_location='cpu')
        model.load_state_dict(checkpoint['model'])
        model.eval()
        del checkpoint
        model: TextSampler = ToCuda(TwoStageSampler(model.module, base_k=5, question_answer_sep_token=tokenizer.question_answer_sep_token))
        # model: TextSampler = ToCuda(TopKSampler(model.module, end_token=tokenizer.question_answer_sep_token, k=5))
        # answer_model: TextSampler = ToCuda(TopKSampler(model.module, k=1))
        # answer_model: TextSampler = ToCuda(BeamSampler(model.module))
        # val_dataset = DataLoader(build_dataset('caption_only', 'val', tokenizer, 'all'), batch_size=1, shuffle=True)
        # val_dataset = DataLoader(build_dataset('answer', 'val', tokenizer, 'all'), batch_size=1, shuffle=True)
        # val_dataset = DataLoader(build_dataset('caption', 'val', tokenizer, 'all', text_encoder=model.module.clip), batch_size=1, shuffle=True)
        batch_size = 64
        val_dataset = DataLoader(build_cc3m_dataset(tokenizer), batch_size=batch_size, shuffle=True, collate_fn=CC3MDataset.collate_fn)
        
        detach = lambda x: x.detach().cpu().tolist()
        
        data = {
            'data': []
        }
        
        types = [
            *[{'answer_type': 'yes/no', 'similar': True} for _ in range(3)],
            *[{'answer_type': 'yes/no', 'similar': False} for _ in range(3)],
            *[{'answer_type': 'number', 'similar': True} for _ in range(3)],
            *[{'answer_type': 'number', 'similar': False} for _ in range(3)],
            *[{'answer_type': 'other', 'similar': True} for _ in range(3)],
            *[{'answer_type': 'other', 'similar': False} for _ in range(3)]
        ]
        
        repeat_sample = len(types)
        
        max_iter = 300000 // batch_size
        
        for i, batch in enumerate(val_dataset):
            start_time = time.time()
            
            tip = batch[0]['tips']
            img_ids = batch[1]
            
            data_to_select = {}
            # target = torch.flatten(batch[1], start_dim=0, end_dim=1)
            
            # img = []
            # for item in zip(*batch[2]):
            #     img.extend(list(item))
            # if img[0] in all_images['images']:
            # if img[0] not in all_images['images']:
                # max_iter += 1
                # continue
            
            # append_to_file('result.txt', 'Choose Image: {0}\n\n'.format(img_ids[0]))
            
            for j in range(repeat_sample):
                batch[0]['tips'] = CaptionProcessor.attach_task_prompt(tip, types[j]['answer_type'], types[j]['similar'], tokenizer)
                
                # append_to_file('result.txt', 'Answer Type: {0}, Similar: {1}\n'.format(types[j]['answer_type'], types[j]['similar']))
                
                prediction, probability = model(batch[0])
                
                # print(probability)
                # _question_prediction = detach(question_prediction)
                # _question_prediction = [item[0:item.index(tokenizer.question_answer_sep_token) + 1] for item in _question_prediction]
                # max_length = max(map(lambda item: len(item), _question_prediction))
                # _question_prediction = [([0] * (max_length - len(item))) + item for item in _question_prediction]
                
                # batch[0]['tips'] = torch.cat([
                #     batch[0]['tips'],
                #     torch.tensor(_question_prediction).long()
                    # torch.where(question_prediction != tokenizer.question_answer_sep_token, question_prediction, 0),
                    # ToCuda(torch.tensor([tokenizer.question_answer_sep_token]).unsqueeze(0).expand(question_prediction.shape[0], -1).long())
                # ], dim=1)
                
                # batch[0]['questions'] = ToCuda(torch.tensor(_question_prediction).long())
                
                # print(convert_items(detach(batch[0]['tips']), tokenizer, tokenizer.question_answer_sep_token))
                
                # answer_prediction = answer_model(batch[0])
                
                # del batch[0]['questions']
                print('sample {}'.format(j))

                for answer, question, prob, img_id in zip(convert_items(detach(prediction), tokenizer, start_token=tokenizer.question_answer_sep_token),
                                                          convert_items(detach(prediction), tokenizer, end_token=tokenizer.question_answer_sep_token),
                                                          # convert_items(detach(question_prediction), tokenizer),
                                                          detach(probability),
                                                          img_ids):
                    img_data = data_to_select.setdefault(img_id, {
                        'yes/no': [],
                        'number': [],
                        'other': [],
                        'all': []
                    })
                    
                    _data = {
                        'question': question,
                        'answer': answer,
                        'prob': prob,
                        'type': types[j]['answer_type']
                    }
                    
                    img_data[types[j]['answer_type']].append(_data)
                    img_data['all'].append(_data)
                    # append_to_file('result.txt', ('Caption: {0} - Question: {1} - Answer: {2} - Probability: {3}\n'.format(
                    #     caption,
                    #     question,
                    #     answer,
                    #     prob
                    # )))
                # append_to_file('result.txt', '\n')
                print('sample {} finished'.format(j))
            # items = map(lambda x: int(x), list(set(img)))
            # all_images['images'].extend(items)
            for img_id, img_data in data_to_select.items():
                selected_data = []
                selected_data.extend(sorted(img_data['yes/no'], key=lambda item: item['prob'], reverse=True)[0:2])
                selected_data.extend(sorted(img_data['number'], key=lambda item: item['prob'], reverse=True)[0:2])
                selected_data.extend(sorted(img_data['other'], key=lambda item: item['prob'], reverse=True)[0:2])
                for _data in selected_data:
                    _data['img_id'] = img_id
                    _data['question_id'] = q_id_gen.q_id
                data['data'].extend(selected_data)
            
            with open('dataset.json', 'w') as f:
                json.dump(data, f, indent=4)
            # with open('images.json', 'w') as f:
            #     json.dump(all_images, f, indent=4)

            if i >= max_iter - 1:
                break
            
            end_time = time.time()
            print('Iter: {} - Step Time: {} - ETA: {}s'.format(i, end_time - start_time, (end_time - start_time) * (max_iter - i - 1)))


def append_to_file(path, content):
    with open(path, 'a') as f:
        f.write(content)


def convert_items(items, tokenizer: Tokenizer, end_token=102, start_token=101):
    def find(_list, item):
        try:
            return _list.index(item)
        except Exception:
            return -1
    
    results = []
    for item in items:
        results.append(' '.join(tokenizer.tokenizer.convert_ids_to_tokens(item[find(item, start_token) + 1:find(item, end_token)])).replace(' ##', ''))
    return results


if __name__ == '__main__':
    main()
