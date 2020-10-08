# -*- coding: utf-8 -*-
# Data algorithm: to find required document types
# use doc2vec vectorizer and some classifiers

import os
import pandas as pd
from ..libcat.mytextpipe.mytextpipe import corpus
import joblib
import logging
import re
import gensim
from uk_stemmer import UkStemmer
from string import punctuation
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, MinMaxScaler


_logger = logging.getLogger(__name__)


class DisableLogger:
    def __enter__(self):
        logging.disable(logging.CRITICAL)

    def __exit__(self, exit_type, exit_value, exit_traceback):
        logging.disable(logging.NOTSET)


class DataTransformer:

    def __init__(self, data_folder='', trained_folder=''):
        self.data_path = data_folder
        self.trained_path = trained_folder

    def fit(self):

        #####################################################################
        # Load csv files
        data_path = self.data_path
        csvs = []
        for root, dirs, files in os.walk(data_path):
            for f in files:
                if f.endswith(".csv"):
                    try:
                        csv = pd.read_csv(os.path.join(data_path, f))
                        csvs.append(csv)
                    except (FileExistsError, IOError, pd.errors.EmptyDataError) as e:
                        _logger.error('{}: {}'.format(f, e))

        txt_data = pd.concat(csvs, ignore_index=True)
        txt_data.fillna(value={'label_id': 0, 'label_name': '?'}, inplace=True)
        # todo: check columns, missing and duplicated
        _logger.info('Loaded {} sentences from {} files'.format(txt_data.shape[0], len(set(txt_data['file'].dropna()))))

        #####################################################################
        # Normalize text
        corp = corpus.HTMLCorpusReader('.', stemmer=UkStemmer(), clean_text=True, language='russian')

        def normalize(text):

            text = text.strip()

            url_pattern = r'https?://\S+|http?://\S+|www\.\S+'
            text = re.sub(pattern=url_pattern, repl=' ', string=text)

            # text = unidecode.unidecode(text)
            text = text.translate(str.maketrans('', '', punctuation))

            # number_pattern = r'\d+'
            # text = re.sub(pattern=number_pattern, repl="nmbr", string=text)
            # text = re.sub(pattern=number_pattern, repl=" ", string=text)

            single_char_pattern = r'\s+[a-zA-Z]\s+'
            text = re.sub(pattern=single_char_pattern, repl=" ", string=text)

            text = gensim.utils.decode_htmlentities(gensim.utils.deaccent(text))

            space_pattern = r'\s+'
            text = re.sub(pattern=space_pattern, repl=" ", string=text)

            return [x for x in corp.text_to_words(text)]

        def read_corpus_df(source_df, tokens_only=False, txt_column='text'):
            for index, row in source_df.iterrows():
                word_lst = normalize(str(row[txt_column]))
                if word_lst:
                    if tokens_only:
                        yield word_lst
                    else:
                        yield gensim.models.doc2vec.TaggedDocument(word_lst, [row['doc2vec_uid']])

        def ivec(word_list, vec_model, epochs=850, alpha=0.025):
            return vec_model.infer_vector(word_list, epochs=epochs)

        def map_label(labels, name=None, index=None):
            if name is not None:
                return labels[name]
            elif index is not None:
                return list(labels.keys())[list(labels.values()).index(index)]
            else:
                raise ValueError("Specify name or number, not both")

        label_dct = {}
        for i, val in enumerate(list(set(txt_data['label_name'].dropna()))):
            label_dct.update({val: i})

        txt_data['doc2vec_uid'] = range(1, len(txt_data.index) + 1)
        train_corpus = list(read_corpus_df(txt_data))

        _logger.info('Prepared train corpus for doc2vec, items count {}'.format(len(train_corpus)))

        #####################################################################
        # Instantiate doc2vec model, train it

        # val_results = [7.4, 50, 100, 2] [6.1, 250, 100, 2] [7.7, 100, 100, 2]
        val_results = [6.1, 300, 200, 2]

        _logger.info('Creating doc2vec model with hyperparameters: vector size {} epochs {} window {} '
                     .format(val_results[1], val_results[2], val_results[3]))

        with DisableLogger():
            model = gensim.models.doc2vec.Doc2Vec(train_corpus,
                                                  vector_size=val_results[1],
                                                  window=val_results[3],
                                                  min_count=1,
                                                  workers=8,
                                                  epochs=val_results[2])

        _logger.info('Doc2vec model is ready, vocabulary size {}'.format(len(model.wv.vocab)))

        #####################################################################
        # Train classifier

        txt_data['cls_uid'] = [-1 for i in range(1, len(txt_data.index) + 1)]

        X, y, cnt = [], [], 0
        for index, row in txt_data.iterrows():
            vec_uid = row['doc2vec_uid']
            if vec_uid in model.docvecs:
                text_vec = model.docvecs[vec_uid]
                X.append(text_vec)
                y.append(map_label(label_dct, name=row['label_name']))
                row['cls_uid'] = cnt
                cnt += 1

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.10, random_state=1)

        _logger.info('Start classifier training')
        _logger.info('Full dataset {}, train {}, test {} sentences'.format(len(y), len(y_train), len(y_test)))

        scaler = StandardScaler()
        scaler.fit(X_train)
        X_train = scaler.transform(X_train)
        X_test = scaler.transform(X_test)

        # https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html
        # activation = {‘identity’, ‘logistic’, ‘tanh’, ‘relu’}
        # solver = {‘lbfgs’, ‘sgd’, ‘adam’}
        # max_iter = 200
        # learning_rate = {‘constant’, ‘invscaling’, ‘adaptive’}
        clf = MLPClassifier(solver='adam', alpha=1e-7, hidden_layer_sizes=(200, 100), random_state=1,
                            activation='logistic', max_iter=2000,
                            learning_rate='adaptive', verbose=False, tol=1e-6)

        # https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html
        # clf = SVC(C=2.0,
        #           kernel='poly', degree=5, gamma='auto', coef0=0.0, shrinking=True, probability=False, tol=0.0001,
        # cache_size=800, verbose=False, max_iter=-1, decision_function_shape='ovr', break_ties=False, random_state=1)
        y_pred = clf.fit(X_train, y_train).predict(X_test)

        doc_cnt = sum([1 for lab in y_test if lab != 0])
        _logger.info('Labels in tests {}'.format(doc_cnt))

        _logger.info('Accuracy {}'.format(accuracy_score(y_pred, y_test)))
        report = str(
            classification_report(y_test, y_pred, zero_division=0,
                                  target_names=list(
                                      [map_label(label_dct, index=i) for i in range(0, len(label_dct))]),
                                  labels=list([map_label(label_dct, name=map_label(label_dct, index=i)) for i in
                                               range(0, len(label_dct))]))
        )
        _logger.info('\n{}'.format(report))

        #####################################################################
        # Save models to file
        trained_path = self.trained_path

        vec_path = os.path.join(trained_path, 'vectorizer.mod')
        model.delete_temporary_training_data(keep_doctags_vectors=True, keep_inference=True)
        joblib.dump(model, vec_path)
        _logger.info('Doc2vec model saved to {}'.format(vec_path))

        clf_path = os.path.join(trained_path, 'classifier.mod')
        joblib.dump(clf, clf_path)
        _logger.info('classifier saved to {}'.format(clf_path))
