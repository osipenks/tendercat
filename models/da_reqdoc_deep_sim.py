# -*- coding: utf-8 -*-
# Data algorithm: to find required document types
# use doc2vec vectorizer and similarity analysis

import csv
import os
import pandas as pd
from ..libcat.mytextpipe.mytextpipe import corpus
import joblib
import logging
import re
import gensim
from uk_stemmer import UkStemmer
import math
from gensim.models import Phrases


_logger = logging.getLogger(__name__)


class DataPipeline:

    def __init__(self, data_folder=None, trained_folder=None, a=None):

        self.info = _logger.info if a is None else a.info
        self.data_folder = data_folder
        self.trained_folder = trained_folder
        self.model_path = os.path.join(self.trained_folder, 'deep_sim.mod')

        self.ngram = None
        self.vectorizer = None
        self.train_column = 'norm_text'
        self.train_df = None
        self.label_stat = None

        self.corp = corpus.HTMLCorpusReader('.', stemmer=UkStemmer(), clean_text=True, language='russian')
        self.word_count = 0

        # Add stop_words
        self.stop_words = self.corp.stop_words.copy()
        self.stop_words += ['в', 'на', 'за', 'із', 'та', 'що', 'як', 'грн', 'гривен', 'або', 'якщо', '2020',
                            'до', 'про', 'як', 'так', 'для', 'від', 'інш', 'щод', 'іх', 'над', 'цьог', 'дат', 'шт',
                            'чи',
                            'мм', '10', 'також', 'під_час', 'при', 'коп', 'мож', 'ма', 'ціє', 'по', 'післ', 'сум',
                            'без',
                            'цим', 'наступн', 'це', '20', 'ус', 'сво', 'час', 'тощ', 'номер', 'місц', 'одн', 'под',
                            'не_пізніш',
                            '12', 'дiаметр', 'менш', 'бут', 'окрем', 'будьяк', 'під', 'ум', 'учасник', 'дня',
                            '[', ']', 'підпис', 'печатк', 'уповноважено', 'особ', 'раз', 'зі', 'isregistry_keywords',
                            'рок', 'рік']
        self.info('Loaded {} stop words'.format(len(self.stop_words)))

        # Add stop_texts
        self.stop_text = []
        if 1 == 1:
            fdir = os.path.join(self.trained_folder)
            for f in os.listdir(fdir):
                if os.path.isfile(os.path.join(fdir, f)):
                    if f.endswith("stop_text.txt"):
            # for root, dirs, files in os.walk(self.trained_folder):
            #     for f in files:
            #         if f.endswith("stop_text.txt"):
                        fname = os.path.join(self.trained_folder, f)
                        with open(fname, "r") as file:
                            for line in file:
                                line_lst = list(line.strip().split(" "))
                                txt = ' '.join(line_lst[1:])
                                self.stop_text.append(txt)
                            self.info('Loaded {} stop texts from {}'.format(len(self.stop_text), fname))
            self.stop_text = list(set(self.stop_text))
            self.info('Total {} stop texts is now in pipeline'.format(len(self.stop_text)))

    def is_stop_text(self, txt):
        return txt in self.stop_text

    def is_stop_word(self, word):
        if len(word) <= 1:
            return True
        if word in ['.', ',', ';', ':', '!', '?']:
            return True
        if word in self.stop_words:
            return True

    def nice_word_form(self, word):
        # Some special cases
        nice_dct = {
            'тендерно': 'тендерн',
            'тендерні': 'тендерн',
            'електронні': 'електронн',
            'договор': 'договір',
            'статт_17': 'ст17',
            'юридично': 'юридичн',
            'юридични': 'юридичн',
            'антикорупціино': 'антикорупціин',
            'банківсько': 'банківськ',
            'будь-яко': 'будь-як',
            'будь-які': 'будь-як',
            'будівельно': 'будівельн',
            'бюджетн': 'бюджет',
            'вартост': 'вартіст',
            'вважают': 'вваж',
            'вважаєт': 'вваж',
            'вимагал': 'вимаг',
            'вимагают': 'вимаг',
            'вимагаєт': 'вимаг',
            'вимог': 'вимаг',
            'випробувальн': 'випробуван',
            'випробуванн': 'випробуван',
            'виробник': 'виробн',
            'виробництв': 'виробн',
            'виробнич': 'виробн',
            'відповідальност': 'відповідальн',
            'відповідальніст': 'відповідальн',
            'державно': 'державн',
        }
        return nice_dct[word] if word in nice_dct else word

    def normalize(self, txt):

        txt = txt.strip()

        url_pattern = r'https?://\S+|http?://\S+|www\.\S+'
        txt = re.sub(pattern=url_pattern, repl=' ', string=txt)

        # number_pattern = r'\d+'
        # txt = re.sub(pattern=number_pattern, repl="nmbr", string=txt)
        # txt = re.sub(pattern=number_pattern, repl=" ", string=txt)

        single_char_pattern = r'\s+[a-zA-Z]\s+'
        txt = re.sub(pattern=single_char_pattern, repl=" ", string=txt)

        txt = gensim.utils.decode_htmlentities(gensim.utils.deaccent(txt))

        space_pattern = r'\s+'
        txt = re.sub(pattern=space_pattern, repl=" ", string=txt)

        return [self.nice_word_form(x)
                for x in self.corp.text_to_words(txt)
                if not self.is_stop_word(x)]

    def text_src(self, source_df, column='norm_text'):
        # Generator for reading texts of selected column
        # Return list of words
        for index, row in source_df.iterrows():
            txt = str(row[column]).strip()
            if txt:
                yield txt.split()

    def calc_word_count(self, source_df, column='norm_text'):
        word_list = []
        for txt in self.text_src(source_df, column):
            for word in txt:
                word_list.append(word)
        word_df = pd.DataFrame(word_list, columns=['word'])
        self.word_count = word_df['word'].nunique()
        return word_df

    def print_most_freq(self, source_df, column, top, reverse=True):
        _freq_word_dct = dict(source_df[column].value_counts())
        for w in sorted(_freq_word_dct, key=_freq_word_dct.get, reverse=reverse):
            print(_freq_word_dct[w], w)
            top -= 1
            if not top:
                break

    def generate_ngrams(self, source_df, n, min_count=10, threshold=20):
        column_name = 'norm_text' if n == 2 else str(n) + 'gram_text'
        prev_column_name = 'norm_text' if (n - 1) == 1 else str((n - 1)) + 'gram_text'

        gram_model = Phrases(self.text_src(source_df, prev_column_name), min_count, threshold)
        gram_list = []
        for txt in self.text_src(source_df, prev_column_name):
            gram_txt = gram_model[txt]
            for word in gram_txt:
                if len(word.split('_')) == n:
                    gram_list.append(word)
        gram_df = pd.DataFrame(gram_list, columns=['word'])
        source_df[str(n) + 'gram_text'] = source_df.apply(
            lambda row: ' '.join(gram_model[row[prev_column_name].split()]), axis=1)

        if not prev_column_name == 'norm_text':
            del source_df[prev_column_name]

        self.ngram = gram_model
        self.train_column = column_name
        return gram_df

    def text_src_to_tagged_docs(self, source_df, txt_column='norm_text'):
        for index, row in source_df.iterrows():
            word_lst = str(row[txt_column]).split()
            if word_lst:
                if len(word_lst) <= 1:
                    continue
                else:
                    yield gensim.models.doc2vec.TaggedDocument(word_lst, [row['doc2vec_uid']])

    def ivec(self, word_list, epochs=850, alpha=0.025):
        if self.vectorizer:
            return self.vectorizer.infer_vector(word_list, epochs=epochs)
        else:
            return []

    def most_similar(self, txt, topn=30):

        similars = []

        if self.ngram:
            word_list = self.ngram[self.normalize(txt)]
        else:
            word_list = self.normalize(txt)
        txt_vector = self.ivec(word_list)
        sims = self.vectorizer.docvecs.most_similar([txt_vector], topn=topn)

        for doc_id, sim in sims:
            found_rows = self.train_df[self.train_df.doc2vec_uid == doc_id]
            similars.append({
                'id': doc_id,
                'label_name': found_rows['label_name'],
                'label_id': found_rows['label_id'],
                'text': found_rows['text'],
                'train_text': found_rows[self.train_column],
                'sim': sim,
            })

        return similars

    def save(self):
        joblib.dump({
            'ngram': self.ngram,
            'vectorizer': self.vectorizer,
            'stop_words': self.stop_words,
            'stop_text': self.stop_text,
            'train_column': self.train_column,
            'train_df': self.train_df,
            'label_stat': self.label_stat,
        }, self.model_path)
        self.info('Model saved to {}'.format(self.model_path))

    def load(self):
        model_dct = joblib.load(self.model_path)
        self.ngram = model_dct['ngram']
        self.vectorizer = model_dct['vectorizer']
        self.stop_words = model_dct['stop_words']
        self.stop_text = model_dct['stop_text']
        self.train_column = model_dct['train_column']
        self.train_df = model_dct['train_df']
        self.label_stat = model_dct['label_stat']
        self.info('Model loaded from {}'.format(self.model_path))

    def update_label_stat(self):

        tdf = self.train_df
        label_freq, label_names, label_norm_freq = {}, {}, {}
        max_count, total_cnt, major_cnt = 0, 0, 0
        for i, row in tdf.groupby('label_id').nunique().iterrows():
            cnt = row[self.train_column]
            label_freq[i] = cnt
            total_cnt += cnt
            if cnt > max_count:
                max_count = cnt
            if i == 1001:
                major_cnt += 1
            label_names[i] = tdf.loc[tdf['label_id'] == i, 'label_name'].iloc[0]
            # calc unique texts count instead

        #major = 7*total_cnt/(total_cnt - major_cnt)
        major = total_cnt / (total_cnt - major_cnt)

        for label_id in label_freq:
            if label_id == 1001:
                label_norm_freq[label_id] = label_freq[label_id]/(max_count * major)
            else:
                label_norm_freq[label_id] = label_freq[label_id]/max_count

        self.label_stat = {
            'freq': label_freq,
            'norm_freq': label_norm_freq,
            'name': label_names,
            'total_cnt': total_cnt,
        }

    def text_label(self, txt, stack=20, sim_pow=3, debug=False):

        sims = self.most_similar(txt, topn=stack)

        labels_cnt = {}
        labels_sim = {}

        for sim in sims:

            try:
                label_id = sim['label_id'].iloc[0]
            except:
                continue

            if label_id in labels_cnt:
                labels_cnt[label_id] += 1
                labels_sim[label_id] += math.pow(sim['sim'], sim_pow)
            else:
                labels_cnt[label_id] = 1
                labels_sim[label_id] = math.pow(sim['sim'], sim_pow)

        labels_score = {}

        for label_id in labels_cnt:
            # Fraction of particular label set
            norm_freq = labels_cnt[label_id] / self.label_stat['norm_freq'][label_id]
            total_norm_freq = norm_freq

            # Look at similarity
            score = total_norm_freq * labels_sim[label_id]

            labels_score[label_id] = score

        winner_id = sorted(labels_score, key=labels_score.get, reverse=True)[0]

        vals = {
            'label_id': winner_id,
            'label_name': self.label_stat['name'][winner_id],

        }

        if debug:
            sims_name = {}
            for w in sorted(labels_score, key=labels_score.get, reverse=True):
                sims_name[self.label_stat['name'][w]] = labels_score[w]
            vals.update({
                'sims': labels_score,
                'sims_named': sims_name,
                'sim': labels_score[winner_id]
            })

        return vals

    def fit(self, data_folder=None, trained_folder=None, a=None):

        self.info = _logger.info if a is None else a.info
        self.data_folder = self.data_folder if data_folder is None else data_folder
        self.trained_folder = self.trained_folder if trained_folder is None else trained_folder

        ################################################
        # Load csv
        csvs = []
        for root, dirs, files in os.walk(self.data_folder):
            for f in files:
                if f.endswith(".csv"):
                    try:
                        csvs.append(pd.read_csv(os.path.join(self.data_folder, f)))
                    except (FileExistsError, IOError, pd.errors.EmptyDataError) as e:
                        _logger.error('{}: {}'.format(f, e))

        df = pd.concat(csvs, ignore_index=True)
        df.fillna(value={'label_id': 1001, 'label_name': '?'}, inplace=True)
        df.label_id = df.label_id.astype(int)

        self.info('Loaded {} training texts from {} files'.format(df.shape[0], len(set(df['file'].dropna()))))

        ################################################
        # Characters count
        df['chr_count'] = df.apply(lambda row: len(row['text']), axis=1)

        stat = {'chr_count_max': df['chr_count'].max(), 'chr_count_min': df['chr_count'].min()}

        self.info('Character counts in texts: min {}, max {},  mean {}\n'
                  .format(stat['chr_count_min'], stat['chr_count_max'], df['chr_count'].mean()))

        ################################################
        # Delete too long sentences, max chr count -1
        start_len = df.shape[0]
        df = df.drop(df[df.chr_count >= stat['chr_count_max'] - 1].index)
        self.info('Deleted {} long texts'.format(start_len - df.shape[0]))

        if 0 == 1:
            top_n = 5
            self.info('\nTop {} most long now: '.format(top_n))
            self.info(df.sort_values('chr_count', ascending=False)['text'].head(top_n))

        ################################################
        # Delete too short sentences, chr count == min
        start_len = df.shape[0]
        max_chr_count = max(3, stat['chr_count_min'])
        df = df.drop(df[df.chr_count <= max_chr_count].index)
        self.info('Deleted {} short texts'.format(start_len - df.shape[0]))

        if 0 == 1:
            top_n = df.shape[0] // 50
            self.info('\nTop {} most short now: '.format(top_n))
            self.info(df.sort_values('chr_count', ascending=True)['text'].head(top_n))

        ################################################
        # Generate normalized text, iter 1
        df['norm_text'] = df.apply(lambda row: str(' '.join(self.normalize(row['text'])).strip()), axis=1)

        # We may unload most frequent texts to disk here

        ################################################
        # Delete stop_texts
        start_len = df.shape[0]
        df = df.drop(df[df['norm_text'].isin(self.stop_text)].index)
        self.info('Deleted {} stop-texts from training corpus'.format(start_len - df.shape[0]))

        ##############################################
        # Words in texts
        word_list = []
        for txt in self.text_src(df, 'norm_text'):
            for word in txt:
                word_list.append(word)
        word_df = pd.DataFrame(word_list, columns=['word'])
        self.info('Found {} unique tokens in texts'.format(word_df['word'].nunique()))

        if 0 == 1:
            top_n = 300
            self.info('\nTop {} most frequent tokens:'.format(top_n))
            self.print_most_freq(word_df, 'word', top_n)

        if 0 == 1:
            top_n = 200
            self.info('\nTop {} rare tokens:\n'.format(top_n))
            self.print_most_freq(word_df, 'word', top_n, reverse=False)

        ##############################################
        # Add rare words to stop list
        freq_word_dct = dict(word_df['word'].value_counts())
        cnt = 0
        for w in freq_word_dct:
            if freq_word_dct[w] == 1:
                self.stop_words.append(w)
                cnt += 1
        self.info('{} rare words added to stop list'.format(cnt))

        ##############################################
        # Remove stop words from norm texts, normalize text, iter 2
        df['norm_text'] = df.apply(lambda row: ' '.join(self.normalize(row['text'])), axis=1)
        self.info('Texts normalized again, stop-words removed from texts')
        word_df = self.calc_word_count(df, 'norm_text')
        self.info('Now {} tokens in vocabulary'.format(self.word_count))

        ##############################################
        # N-grams
        # 2-grams
        gram_df = self.generate_ngrams(df, 2, min_count=20, threshold=10)
        self.info('\n{} 2-grmas found'.format(gram_df['word'].nunique()))
        word_df = self.calc_word_count(df, '2gram_text')
        self.info('Now {} tokens in vocabulary'.format(self.word_count))
        if 0 == 1:
            top_n = 100
            self.info('\nTop {} most frequent 2-grams:\n'.format(top_n))
            self.print_most_freq(gram_df, 'word', top_n)

        if 1 == 1:
            # 3-grams
            gram_df = self.generate_ngrams(df, 3, min_count=10, threshold=30)
            self.info('\n{} 3-grmas found'.format(gram_df['word'].nunique()))
            word_df = self.calc_word_count(df, '3gram_text')
            self.info('Now {} tokens in vocabulary'.format(self.word_count))
            if 0 == 1:
                top_n = 50
                self.info('\nTop {} most frequent 3-grams:\n'.format(top_n))
                self.print_most_freq(gram_df, 'word', top_n)

        if 0 == 1:
            # 4-grams
            gram_df = self.generate_ngrams(df, 4, min_count=7, threshold=40)
            self.info('\n{} 4-grmas found'.format(gram_df['word'].nunique()))
            word_df = self.calc_word_count(df, '4gram_text')
            self.info('Now {} tokens in vocabulary'.format(self.word_count))
            if 1 == 1:
                top_n = 10
                self.info('\nTop {} most frequent 4-grams:\n'.format(top_n))
                self.print_most_freq(gram_df, 'word', top_n)

        if 0 == 1:
            # Show words in abc order
            top_n = 2500
            self.info('\nTop {} most frequent words:'.format(top_n))
            word_df = self.calc_word_count(df, '2gram_text')
            word_dct = dict(word_df['word'])
            words = []
            for w in sorted(word_dct, key=word_dct.get, reverse=False):
                if not word_dct[w] in words:
                    words.append(word_dct[w])
                    self.info(word_dct[w])
                    top_n -= 1
                    if not top_n:
                        break

        ##############################################
        # Doc2vec
        df['doc2vec_uid'] = range(1, len(df.index) + 1)
        train_corpus = list(self.text_src_to_tagged_docs(df, txt_column=self.train_column))
        self.info('\nPrepeared train corpus for Doc2vec, {} texts'.format(len(train_corpus)))
        # print(train_corpus[500:800])
        # [6.1, 300, 200, 2] [7.4, 50, 100, 2] [6.1, 250, 100, 2] [7.7, 100, 100, 2]
        vector_size, epochs, window = 300, 200, 2
        self.info('Creating model with hyperparameters: vector_sizes {} epochs {} window {} ...\n'
                  .format(vector_size, epochs, window))
        self.vectorizer = gensim.models.doc2vec.Doc2Vec(train_corpus, vector_size=vector_size, window=window,
                                                        min_count=1, workers=8, epochs=epochs)
        self.info('Doc2vec model is ready, vocabulary {}'.format(len(self.vectorizer.wv.vocab)))

        self.train_df = df
        self.update_label_stat()
        self.save()

    def transform(self, input_file=None, output_file=None, trained_folder=None, a=None):

        self.info = _logger.info if a is None else a.info
        self.trained_folder = self.trained_folder if trained_folder is None else trained_folder

        self.load()
        self.update_label_stat()

        # Load input csv file
        if not os.path.isfile(input_file):
            return

        df = pd.read_csv(input_file)
        df.fillna(value={'label_id': 1001, 'label_name': '?'}, inplace=True)
        self.info('Loaded {} sentences, {} files'.format(df.shape[0], len(set(df['file'].dropna()))))

        ################################################
        # Characters count
        df['chr_count'] = df.apply(lambda row: len(row['text']), axis=1)

        stat = {'chr_count_max': df['chr_count'].max(), 'chr_count_min': df['chr_count'].min()}

        self.info('Character counts in texts: min {}, max {},  mean {}\n'
                  .format(stat['chr_count_min'], stat['chr_count_max'], df['chr_count'].mean()))

        ################################################
        # Delete too long sentences, max chr count -1
        start_len = df.shape[0]
        df = df.drop(df[df.chr_count >= stat['chr_count_max'] - 1].index)
        self.info('Deleted {} long texts'.format(start_len - df.shape[0]))

        if 0 == 1:
            top_n = 5
            self.info('\nTop {} most long now: '.format(top_n))
            self.info(df.sort_values('chr_count', ascending=False)['text'].head(top_n))

        ################################################
        # Delete too short sentences, chr count == min
        start_len = df.shape[0]
        max_chr_count = max(3, stat['chr_count_min'])
        df = df.drop(df[df.chr_count <= max_chr_count].index)
        self.info('Deleted {} short texts'.format(start_len - df.shape[0]))

        if 0 == 1:
            top_n = df.shape[0] // 50
            self.info('\nTop {} most short now: '.format(top_n))
            self.info(df.sort_values('chr_count', ascending=True)['text'].head(top_n))

        ##############################################
        # Generate normalized text, iter 1
        df['norm_text'] = df.apply(lambda row: str(' '.join(self.normalize(row['text'])).strip()), axis=1)

        # We may unload most frequent texts to disk here

        ##############################################
        # Delete stop_texts
        start_len = df.shape[0]
        df = df.drop(df[df['norm_text'].isin(self.stop_text)].index)
        self.info('Deleted {} stop-texts from training corpus'.format(start_len - df.shape[0]))

        ##############################################
        # Words in texts
        word_list = []
        for txt in self.text_src(df, 'norm_text'):
            for word in txt:
                word_list.append(word)
        word_df = pd.DataFrame(word_list, columns=['word'])
        self.info('Found {} unique tokens in texts'.format(word_df['word'].nunique()))

        if 0 == 1:
            top_n = 300
            self.info('\nTop {} most frequent tokens:'.format(top_n))
            self.print_most_freq(word_df, 'word', top_n)

        if 0 == 1:
            top_n = 200
            self.info('\nTop {} rare tokens:\n'.format(top_n))
            self.print_most_freq(word_df, 'word', top_n, reverse=False)

        ##############################################
        # Add rare words to stop list
        freq_word_dct = dict(word_df['word'].value_counts())
        cnt = 0
        for w in freq_word_dct:
            if freq_word_dct[w] == 1:
                self.stop_words.append(w)
                cnt += 1
        self.info('{} rare words added to stop list'.format(cnt))

        ##############################################
        # Remove stop words from norm texts, normalize text, iter 2
        if 1 == 1:
            df['norm_text'] = df.apply(lambda row: ' '.join(self.normalize(row['text'])), axis=1)
            self.info('Texts normalized again, stop-words removed from texts')
            word_df = self.calc_word_count(df, 'norm_text')
            self.info('Now {} tokens in vocabulary'.format(self.word_count))

        with open(output_file, mode='w') as file:
            csv_fields = ['label_id', 'label_name', 'text', 'text_id', 'file', 'tender']
            writer = csv.DictWriter(file, fieldnames=csv_fields, delimiter=',')
            writer.writeheader()
            self.info('Start classifier')
            label_cnt = 0
            label_set = set()
            topn = 20000

            for i, row in df.iterrows():
                text = row['norm_text']
                if not isinstance(text, str):
                    continue

                #sim = self.text_label(text, stack=25, sim_pow=19, debug=False)
                sim = self.text_label(text, stack=1, sim_pow=1, debug=False)


                if 0 == 1:
                    self.info('\n------------------')
                    self.info('{}'.format(text))
                    self.info('{}\n'.format(self.normalize(text)))

                    self.info('Winner: {} {}'.format(sim['label_id'], sim['label_name']))
                    sim_names = sim['sims_named']
                    for w in sorted(sim_names, key=sim_names.get, reverse=True):
                        self.info('{} {}'.format(sim_names[w], w))

                label_id = sim['label_id']
                label_name = sim['label_name']

                if not label_name == '?':
                    label_cnt += 1
                    label_set.add(label_name)

                val = {'label_id': '' if label_name == '?' else label_id,
                       'label_name': '' if label_name == '?' else label_name,
                       'text': text,
                       'text_id': df['text_id'][i],
                       }
                writer.writerow(val)

                topn -= 1
                if topn == 0:
                    break

            self.info('Labeled {} sentences with {} labels'.format(label_cnt, len(label_set)))
