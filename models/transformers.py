from ..libcat.mytextpipe import mytextpipe
import os
import logging
from uk_stemmer import UkStemmer
import pandas as pd
from gensim import corpora, similarities
from gensim import models as gensim_models
from statistics import mean
from random import randrange
import csv

_logger = logging.getLogger(__name__)
PROCESSING_FOLDER = '~'


def _get_processing_folder():
    return PROCESSING_FOLDER


def temp(request_csv, response_csv):
    text_lst = []

    with open(request_csv, mode='r') as f:
        reader = csv.DictReader(f)
        for line in reader:
            text_lst.append(line)
        f.close()

    with open(response_csv, mode='w') as f:
        csv_fields = ['id', 'text', 'file', 'category', 'label', 'score']
        writer = csv.DictWriter(f, fieldnames=csv_fields, delimiter=',')
        writer.writeheader()
        for item in text_lst:
            writer.writerow({
                'id': item['id'],
                'text': item['text'],
                'file': item['file'],
                'category': item['category'],
                'label': 1,
                'score': 7.0
            })
        f.close()


def doc_type_similarity(request_csv, response_csv):

    # 1. Load data from csv file
    sents_df = pd.read_csv(request_csv)

    # 2. Normalize text, get sentences as list of words
    corp = mytextpipe.corpus.HTMLCorpusReader(language='russian', clean_text=True)
    corp.stemmer = UkStemmer()

    sents = []
    for index, row in sents_df.iterrows():
        sent = row['text']
        word_list = ' '.join(corp.text_to_words(sent)).split()
        sents.append(word_list)

    # list of sentences (list of word lists)
    texts = [[token for token in sent] for sent in sents]
    _logger.info('Loaded {} tender sentences for similarities calculation'.format(len(texts)))

    # 2. Load labeled dataset
    labeled_df = pd.read_csv(os.path.join(_get_processing_folder(), 'model', 'labeled.csv'))
    _logger.info('Loaded {} labeled sentences'.format(labeled_df.shape[0]))

    # 3. Normalize and split labeled sentences in word lists
    labeled_sents = []
    for index, row in labeled_df.iterrows():
        sent = row['Sentence']
        word_list = ' '.join(corp.text_to_words(sent)).split()
        labeled_sents.append(word_list)

    # labeled list of sentences (list of lists of words)
    labeled_texts = [[token for token in sent] for sent in labeled_sents]

    # 4. Calculate labeled similarity index
    lexicon = corpora.Dictionary(labeled_texts)
    feature_cnt = len(lexicon.token2id)
    _logger.info('Tokens in labeled sents {}'.format(feature_cnt))

    corpus = [lexicon.doc2bow(text) for text in labeled_texts]

    tfidf = gensim_models.TfidfModel(corpus)
    sim_index = similarities.SparseMatrixSimilarity(tfidf[corpus], num_features=feature_cnt)

    # Calculate similarities for tender sentences
    sim_stats = []
    cnt = 0
    for sent in texts:
        sent_vector = lexicon.doc2bow(sent)
        sim = sim_index[tfidf[sent_vector]]
        sim_stats.append({
            'sent': ' '.join(sent),
            'sum': sum(sim),
            'mean': mean(sim),
            'original': sents_df['text'][cnt],
            'chunk_id': sents_df['id'][cnt]
        })
        cnt += 1
    _logger.info('Similarities calculated for {} tender sentences'.format(len(sim_stats)))

    sort_by = 'mean'
    threshold = 0.05

    with open(response_csv, mode='w') as f:
        csv_fields = ['id', 'text', 'file', 'category', 'label', 'score']
        writer = csv.DictWriter(f, fieldnames=csv_fields, delimiter=',')
        writer.writeheader()

        for stat in sim_stats:
            chunk_id = int(stat['chunk_id'])
            metric_val = float(stat[sort_by])
            is_req_doc = True if metric_val > threshold else False

            if is_req_doc:
                random_lab = randrange(9)
                random_lab += 1
                writer.writerow({
                    'id': chunk_id,
                    'text': '',
                    'file': '',
                    'category': '',
                    'label': random_lab,
                    'score': metric_val
                })
            else:
                writer.writerow({
                    'id': chunk_id,
                    'text': '',
                    'file': '',
                    'category': '',
                    'label': 0,
                    'score': metric_val
                })
        f.close()
