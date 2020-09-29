# -*- coding: utf-8 -*-

import os
import re
import sys
from bs4 import BeautifulSoup
from ..libcat.mytextpipe.mytextpipe import corpus_transformer, corpus
import logging

_logger = logging.getLogger(__name__)


def file_extension_supported(ext):
    supported_ext = ['.csv', '.doc', '.docx', '.eml', '.epub', '.htm', '.html', '.msg', '.txt', '.json', '.log',
                     '.odt', '.ogg', '.pdf', '.pptx', '.ps', '.psv', '.xls', '.xlsx',
                     '.rtf']
    return ext in supported_ext


def file_to_html(args_dict):

    doc_id = args_dict['doc_id']
    source = args_dict['corpus']
    target = args_dict['target']

    proc_folder = doc_id.split(os.path.sep)[0]

    src_folder = os.path.join(source.root, proc_folder)
    dest_folder = os.path.join(target.root, proc_folder)

    if not os.path.isdir(dest_folder):
        os.mkdir(dest_folder)

    file, ext = os.path.splitext(os.path.basename(doc_id))

    src_file_name = os.path.join(src_folder, file) + ext
    new_doc_id = os.path.join(proc_folder, file) + '.html'

    if not file_extension_supported(ext):
        return False

    # extract text from doc file via libreoffice
    if ext in ['.doc', '.docx', '.rtf']:
        _logger.info("Converting {} to html".format(src_file_name))
        # run headless libreofice to convert doc to html
        libre_cmd = '/usr/bin/soffice --headless --convert-to html:\"HTML\" '

        out_dir = ''.join([' --outdir \"', dest_folder, '\"'])

        sys_cmd = ''.join([libre_cmd, '\"', src_file_name, '\"', out_dir])

        os.system(sys_cmd)

    # extract text from pdf file
    elif ext in ['.pdf']:
        pass

    # delete pictures after extraction
    html_ext = ['.htm', '.html']
    for f in os.listdir(dest_folder):
        ext = os.path.splitext(f)[1]
        if ext.lower() not in html_ext:
            abs_path = os.path.join(dest_folder, f)
            if os.path.isfile(abs_path):
                try:
                    os.remove(abs_path)
                except:
                    _logger.warning("Error {} removing file {}".format(sys.exc_info()[0], abs_path))
                    return

    args_dict['doc_id'] = new_doc_id


def prozorro_file_to_html_postpoces(args_dict):

    doc_id = args_dict['doc_id']
    corp = args_dict['corpus']

    src_file_name = corp.id_to_abspath(doc_id)

    if not src_file_name:
        return

    try:
        with open(src_file_name, 'r') as f:
            html = f.read()
            f.close()
    except:
        _logger.warning("Error {} reading file {}".format(sys.exc_info()[0], src_file_name))
        return

    # Process Text

    # remove redundant spaces, line breaks, etc
    html = html.replace('&nbsp', ' ')
    html = html.replace('\r', ' ')
    html = html.replace('\t', ' ')
    html = html.replace(' ;', ';')
    html = html.replace(' ,', ',')
    html = html.replace(' .', '.')
    html = html.replace(' :', ':')
    html = html.replace(':;', ': ')

    html = ' '.join(html.split())

    # remove sequences ... ,,, ;;; etc
    html = re.sub(r';{2,}', ';', html)
    html = re.sub(r',{2,}', ',', html)
    # html = re.sub(r'\.{2,}','.', html) ???
    html = re.sub(r':{2,}', ':', html)

    # Process HTML

    soup = BeautifulSoup(html, 'html.parser')

    # remove html tag attributes
    remove_html_tag_attrs(soup)

    # remove not important tags
    remove_tags = ['style', 'br', 'strike', 'sdfield']
    removals = soup.find_all(remove_tags)
    for match in removals:
        match.decompose()

    # unwrap 'tags
    unwrap_tags = ['font', 'span', 'i', 'b', 'u', 'sub', 'center', 'li', 'ol', 'ul', 'dl', 'dd', 'a']
    tags = soup.find_all(unwrap_tags)
    for tag in tags:
        tag.unwrap()

    # remove all empty tags
    tag_white_list = []
    for tag in soup.find_all():

        if tag.name in tag_white_list:
            continue

        tag_text = str(tag.text)
        tag_text = tag_text.replace(' ', '')
        tag_text = tag_text.replace('\n', '')

        if not tag_text:
            tag.decompose()

    # process all tables
    decompose_tables(soup)

    # if end of paragraph is not a point
    # and next paragraph begins with small letter, join them
    sent_ends = ['.', ':']

    for p in soup.find_all('p'):
        p_text = str(p.text).strip()
        if not p_text:
            continue

        last_chr = p_text[-1]
        if last_chr in sent_ends:
            continue

        next_p = p.findNext('p')
        if next_p:
            next_p_text = str(next_p.text).strip()
            if not next_p_text:
                continue
            first_chr = next_p_text[0]
            if first_chr.isupper():
                continue
            if first_chr.isdigit():
                continue
            if first_chr in ['-']:
                continue

            next_p.string = ' '.join([p_text, next_p_text])
            p.decompose()

    new_html = str(soup)

    # clean some artifacts
    new_html = new_html.replace('.;', '. ')
    new_html = new_html.replace(');', ') ')
    new_html = new_html.replace(';;', '; ')
    new_html = new_html.replace(',;', ', ')

    # Pozorro special cases

    # Some artifacts, like 'до ст.  16 Закону України...'
    new_html = re.sub(r'(\s+)п. +(\d+)', r'\1п.\2', new_html)
    new_html = re.sub(r'(\s+)ч. +(\d+)', r'\1ч.\2', new_html)
    new_html = re.sub(r'(\s+)ст. +(\d+)', r'\1ст.\2', new_html)

    # multiply ;;;; between alphanumerics
    new_html = re.sub(r'(\w+|\d+);+(\w+|\d+)', r'\1 \2', new_html)

    # буд.ХХ
    new_html = re.sub(r'\s{0,}буд[.{1}]\s{0,}', r'буд. ', new_html)
    # т.ч.ПДВ
    new_html = re.sub(r"\s{1,}т.ч.\s{0,}", r' т.ч. ', new_html)

    # links
    new_html = re.sub(r'https?://\S+|www\.\S+', r'', new_html)
    new_html = re.sub(r'http?://\S+|www\.\S+', r'', new_html)

    try:
        if os.path.isfile(src_file_name):
            with open(src_file_name, 'w') as f:
                f.write(new_html)
                f.close()
    except:
        _logger.warning("Error {} occurred reading file {}".format(sys.exc_info()[0], src_file_name))
        return

    return


def table_cells_to_one_p(soup, cells):
    para = ''

    try:
        for cell in cells:
            for p in cell.findAll('p'):
                para += str(p.text)
                p.decompose()
            cell.unwrap()
    except ValueError:
        print("An ValueError occurred in table_cells_to_one_p {}".format(sys.exc_info()[0]))
        return ''
    except:
        print("Unexpected error occurred in table_cells_to_one_p {}".format(sys.exc_info()[0]))
        raise

    new_para = None
    if para:
        new_para = soup.new_tag('p')
        new_para.string = para
    return new_para


def table_column_count(table_tag):
    max_columns = 0
    rows = table_tag.findChildren(['th', 'tr'])
    for row in rows:
        cells = row.findChildren('td')
        cells_count = len(cells)
        if cells_count > max_columns:
            max_columns = cells_count
    return max_columns


def table_row_count(table_tag):
    rows = table_tag.findChildren(['th', 'tr'])
    return len(rows)


def remove_html_tag_attrs(soup, whitelist=tuple()):
    for tag in soup.findAll(True):
        for attr in [attr for attr in tag.attrs if attr not in whitelist]:
            del tag[attr]
    return soup


def decompose_tables(soup):
    for table_tag in soup.find_all('table'):
        row_count = table_row_count(table_tag)

        # one or two rows, join all cell paragraphs in one
        if row_count == 1 or row_count == 2:

            rows = table_tag.findChildren(['th', 'tr'])
            for row in rows:
                cells = row.findChildren('td')
                paragraph = table_cells_to_one_p(soup, cells)
                if paragraph:
                    row.append(paragraph)
                try:
                    row.unwrap()
                except ValueError:
                    print("An ValueError occurred unwrapping table row {}".format(sys.exc_info()[0]))
                except:
                    print("Unexpected error occurred unwrapping table row {}".format(sys.exc_info()[0]))
                    raise

            try:
                table_tag.unwrap()
            except ValueError:
                print("An ValueError occurred unwrapping table tag {}".format(sys.exc_info()[0]))
            except:
                print("Unexpected error occurred in unwrapping table tag {}".format(sys.exc_info()[0]))
                raise

        else:
            # many rows in ta
            column_count = table_column_count(table_tag)

            # only one column in table, join one row in one paragraph
            if column_count == 1:
                rows = table_tag.findChildren(['th', 'tr'])
                for row in rows:
                    cells = row.findChildren('td')
                    paragraph = table_cells_to_one_p(soup, cells)
                    if paragraph:
                        row.append(paragraph)

                try:
                    table_tag.unwrap()
                except ValueError:
                    print("An ValueError occurred unwrapping table tag {}".format(sys.exc_info()[0]))
                except:
                    print("Unexpected error occurred in unwrapping table tag {}".format(sys.exc_info()[0]))
                    raise
            else:
                # first column contain numbers only, join with second column
                rows = table_tag.findChildren(['th', 'tr'])
                for row in rows:
                    cells = row.findChildren('td')

                    if len(cells) == 1:
                        continue
                    cell_text = ''
                    for cell in cells:
                        for any_tag in cell.findChildren():
                            cell_text += str(any_tag.text)
                        break  # check first column only

                    cell_text = cell_text.strip()

                    if re.match('^[\w. №]{1,9}$', cell_text):
                        child_ps = cells[1].findChildren('p')
                        if child_ps:
                            first_p = child_ps[0]
                            first_p.string = ' '.join([cell_text, str(first_p.text).strip()])
                            cell.decompose()

                # unwrap table

                try:
                    rows = table_tag.findChildren(['th', 'tr'])
                    for row in rows:
                        cells = row.findChildren('td')
                        for cell in cells:
                            cell.unwrap()
                        row.unwrap()
                    table_tag.unwrap()
                except ValueError:
                    print("An ValueError occurred unwrapping table tag {}".format(sys.exc_info()[0]))
                except:
                    print("Unexpected error occurred in unwrapping table tag {}".format(sys.exc_info()[0]))
                    raise

    return soup


def prozorro_file_to_html(tender_ids, file_dir, html_dir):

    file_corp = corpus.FileCorpusReader(file_dir)
    html_corp = corpus.FileCorpusReader(html_dir)

    tr = corpus_transformer.CorpusTransformer(file_corp, html_corp, file_corp.ids(categories=tender_ids))

    tr.transform([('file_to_html', file_to_html, file_corp),
                  ('html_post_processing', prozorro_file_to_html_postpoces, html_corp)],
                 {'file_to_html': {'target': html_corp}},
                 debug=True)


def main():
    file_dir = '/home/od13/addons/tender_cat/data/file'
    html_dir = '/home/od13/addons/tender_cat/data/html'

    tenders = ['UA-2017-06-26-000519-b',
               'UA-2018-09-20-001357-a'
               ]

    prozorro_file_to_html(tenders, file_dir, html_dir)


if __name__ == "__main__":
    main()
