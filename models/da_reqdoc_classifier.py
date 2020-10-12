# -*- coding: utf-8 -*-
# Data algorithm: to find required document types
# use doc2vec vectorizer and some classifiers

import csv
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
from sklearn.preprocessing import StandardScaler
from imblearn.under_sampling import RandomUnderSampler
from collections import Counter


_logger = logging.getLogger(__name__)


class DisableLogger:
    def __enter__(self):
        logging.disable(logging.CRITICAL)

    def __exit__(self, exit_type, exit_value, exit_traceback):
        logging.disable(logging.NOTSET)


class DataTransformer:

    def fit(self, data_folder=None, trained_folder=None, a=None):

        log = _logger if a is None else a

        #####################################################################
        # Load csv files
        csvs = []
        for root, dirs, files in os.walk(data_folder):
            for f in files:
                if f.endswith(".csv"):
                    try:
                        csvfile = pd.read_csv(os.path.join(data_folder, f))
                        csvs.append(csvfile)
                    except (FileExistsError, IOError, pd.errors.EmptyDataError) as e:
                        log.error('{}: {}'.format(f, e))

        txt_data = pd.concat(csvs, ignore_index=True)
        txt_data.fillna(value={'label_id': 1001, 'label_name': '?'}, inplace=True)
        txt_data.label_id = txt_data.label_id.astype(int)
        # todo: check columns, missing and duplicated
        log.info('Loaded {} sentences from {} files'.format(txt_data.shape[0], len(set(txt_data['file'].dropna()))))

        #####################################################################
        # Normalize text
        corp = corpus.HTMLCorpusReader('.', stemmer=UkStemmer(), clean_text=True, language='russian')
        corp.stop_words += ['в', 'на', 'за', 'із', 'та', 'що', 'як', 'грн', 'гривен', 'коп', 'або', 'якщо', '2020']

        def normalize(text):

            text = text.strip()

            url_pattern = r'https?://\S+|http?://\S+|www\.\S+'
            text = re.sub(pattern=url_pattern, repl=' ', string=text)

            # text = unidecode.unidecode(text)
            text = text.translate(str.maketrans('', '', punctuation))

            single_char_pattern = r'\s+[a-zA-Z]\s+'
            text = re.sub(pattern=single_char_pattern, repl=" ", string=text)

            text = gensim.utils.decode_htmlentities(gensim.utils.deaccent(text))

            space_pattern = r'\s+'
            text = re.sub(pattern=space_pattern, repl=" ", string=text)

            return [x for x in corp.text_to_words(text) if len(x) > 1]

        def read_corpus_df(source_df, tokens_only=False, txt_column='text'):
            for index, row in source_df.iterrows():
                word_lst = normalize(str(row[txt_column]))
                if word_lst:

                    if len(word_lst) <= 1:
                        continue

                    if tokens_only:
                        yield word_lst
                    else:
                        yield gensim.models.doc2vec.TaggedDocument(word_lst, [row['doc2vec_uid']])

        def map_label(labels, name=None, index=None):
            if name is not None:
                return labels[name]
            elif index is not None:
                return list(labels.keys())[list(labels.values()).index(index)]
            else:
                raise ValueError("Specify name or number, not both")

        label_dct = {}
        for i, row in txt_data.iterrows():
            label_dct.update({row['label_name']: row['label_id']})

        txt_data['doc2vec_uid'] = range(1, len(txt_data.index) + 1)
        train_corpus = list(read_corpus_df(txt_data))

        log.info('Prepared train corpus for doc2vec, items count {}'.format(len(train_corpus)))

        #####################################################################
        # Instantiate doc2vec model, train it

        # val_results = [7.4, 50, 100, 2] [6.1, 250, 100, 2] [7.7, 100, 100, 2]
        val_results = [6.1, 300, 200, 2]

        log.info('Creating doc2vec model with hyperparameters: vector size {} epochs {} window {} '
                 .format(val_results[1], val_results[2], val_results[3]))

        with DisableLogger():
            model = gensim.models.doc2vec.Doc2Vec(train_corpus,
                                                  vector_size=val_results[1],
                                                  window=val_results[3],
                                                  min_count=1,
                                                  workers=8,
                                                  epochs=val_results[2])

        log.info('Doc2vec model is ready, vocabulary size {}'.format(len(model.wv.vocab)))

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

        if 1 == 1:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=1)


        log.info('Start classifier training')
        log.info('Full dataset {}, train {}, test {} sentences'.format(len(y), len(y_train), len(y_test)))

        scaler = StandardScaler()
        scaler.fit(X_train)
        X_train = scaler.transform(X_train)
        X_test = scaler.transform(X_test)

        clf = MLPClassifier(solver='adam', alpha=1e-7, hidden_layer_sizes=(200, 100), random_state=1,
                            activation='logistic', max_iter=3000,
                            learning_rate='adaptive', verbose=False, tol=1e-6)

        y_pred = clf.fit(X_train, y_train).predict(X_test)

        doc_cnt = sum([1 for lab in y_test if lab != 0])
        log.info('Labels in tests {}'.format(doc_cnt))

        log.info('Accuracy {}'.format(accuracy_score(y_pred, y_test)))
        report = str(
            classification_report(y_test, y_pred, zero_division=0,
                                  target_names=list([map_label(label_dct, index=label_dct[val]) for val in label_dct]),
                                  labels=list(
                                      [map_label(label_dct, name=map_label(label_dct, index=label_dct[val])) for val in
                                       label_dct])))
        log.info('\n{}'.format(report))

        #####################################################################
        # Save models to file

        vec_path = os.path.join(trained_folder, 'vectorizer.mod')
        model.delete_temporary_training_data(keep_doctags_vectors=True, keep_inference=True)
        joblib.dump(model, vec_path)
        log.info('doc2vec model saved to {}'.format(vec_path))

        clf_path = os.path.join(trained_folder, 'classifier.mod')
        joblib.dump(clf, clf_path)
        log.info('classifier saved to {}'.format(clf_path))

        label_path = os.path.join(trained_folder, 'labels.mod')
        joblib.dump(label_dct, label_path)
        log.info('Labels saved to {}'.format(label_path))

        scaler_path = os.path.join(trained_folder, 'scaler.mod')
        joblib.dump(scaler, scaler_path)
        log.info('Scaler saved to {}'.format(label_path))

    def transform(self, input_file=None, output_file=None, trained_folder=None, a=None):

        # Folders
        vct_path = os.path.join(trained_folder, 'vectorizer.mod')
        clf_path = os.path.join(trained_folder, 'classifier.mod')
        label_path = os.path.join(trained_folder, 'labels.mod')
        scaler_path = os.path.join(trained_folder, 'scaler.mod')

        # Load input csv file
        txt_data = pd.read_csv(input_file)
        txt_data.fillna(value={'label_id': 0, 'label_name': '?'}, inplace=True)
        a.info('Loaded {} sentences, {} files'.format(txt_data.shape[0], len(set(txt_data['file'].dropna()))))

        # Load models: vectorizer and classifier
        vct = joblib.load(vct_path)
        a.info('Vectorizer loaded, vectors {}, vocabulary {} words'.format(len(vct.docvecs), len(vct.wv.vocab)))
        clf = joblib.load(clf_path)
        a.info('Classifier loaded, layers {}, outputs {}'.format(clf.n_layers_, clf.n_outputs_))
        label_dct = joblib.load(label_path)
        a.info('Loaded {} labels'.format(len(label_dct)))
        scaler = joblib.load(scaler_path)
        a.info('Scaler loaded')

        corp = corpus.HTMLCorpusReader('.', stemmer=UkStemmer(), clean_text=True, language='russian')
        corp.stop_words += ['в', 'на', 'за', 'із', 'та', 'що', 'як', 'грн', 'гривен', 'коп', 'або', 'якщо', '2020']

        def normalize(txt):

            txt = txt.strip()

            url_pattern = r'https?://\S+|http?://\S+|www\.\S+'
            txt = re.sub(pattern=url_pattern, repl=' ', string=txt)

            # txt = unidecode.unidecode(txt)
            txt = txt.translate(str.maketrans('', '', punctuation))

            single_char_pattern = r'\s+[a-zA-Z]\s+'
            txt = re.sub(pattern=single_char_pattern, repl=" ", string=txt)

            txt = gensim.utils.decode_htmlentities(gensim.utils.deaccent(txt))

            space_pattern = r'\s+'
            txt = re.sub(pattern=space_pattern, repl=" ", string=txt)

            return [x for x in corp.text_to_words(text) if len(x) > 1]

        def ivec(word_list, model, epochs=850, alpha=0.025):
            return model.infer_vector(word_list, epochs=epochs)

        def map_label(labels, name=None, index=None):
            if name is not None:
                return labels[name]
            elif index is not None:
                return list(labels.keys())[list(labels.values()).index(index)]
            else:
                raise ValueError("Specify name or number, not both")

        predictions = []

        with open(output_file, mode='w') as file:
            csv_fields = ['label_id', 'label_name', 'text', 'text_id', 'file', 'tender']
            writer = csv.DictWriter(file, fieldnames=csv_fields, delimiter=',')
            writer.writeheader()
            a.info('Start classifier')
            label_cnt = 0
            label_set = set()

            for i in range(1, txt_data.shape[0]):
                text = txt_data['text'][i]
                if not isinstance(text, str):
                    continue

                text_vector = ivec(normalize(text), vct)
                prediction = clf.predict(scaler.transform([text_vector]))
                label_id = prediction[0]
                label_name = map_label(label_dct, index=label_id)
                predictions.append((label_id, label_name, text))

                if not label_name == '?':
                    label_cnt += 1
                    label_set.add(label_name)

                val = {'label_id': '' if label_name == '?' else label_id,
                       'label_name': '' if label_name == '?' else label_name,
                       'text': text,
                       'text_id': txt_data['text_id'][i],
                       }
                writer.writerow(val)

            a.info('Labeled {} sentences with {} labels'.format(label_cnt, len(label_set)))

        """ Stub 
        with open(input_file, mode='r') as ifile:
            with open(output_file, mode='w') as ofile:
                reader = csv.DictReader(ifile)

                csv_fields = ['label_id', 'label_name', 'text', 'text_id', 'file', 'tender']
                writer = csv.DictWriter(ofile, fieldnames=csv_fields, delimiter=',')
                writer.writeheader()

                my_randoms = random.sample(range(50), 10)

                r = random.randrange(0, 10, 1)
                i = 0

                for line in reader:
                    i += 1
                    val = {'label_id': '',
                           'label_name': '',
                           'text': line['text'],
                           'text_id': int(line['text_id']),
                           'file': line['file'],
                           'tender': line['tender'],
                           }
                    writer.writerow(val)
            """
