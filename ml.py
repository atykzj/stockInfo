

def readReturnLink(s):
    import pandas as pd
    import requests
    from bs4 import BeautifulSoup # Web scrape
    
    t = ''.join(x for x in s if x.isalpha())
    t = t.lower()
    tickCIK = pd.read_csv('ticker-cik.txt', sep='\\t', index_col=False, \
                            names=['Tick', 'CIK'], engine='python')

    foo = str(tickCIK.loc[tickCIK['Tick'] == t]['CIK'].item())
    # We know the html, so we add the keyword. But for CIK keyword,
    #need to make sure it fills up 10 values.
    while len(foo)<10:
        foo = '0'+foo
    fullHTML = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=" + foo + "&type=10-k%25&dateb=&owner=exclude&start=0&count=40&output=atom"
    requestLink = requests.get(fullHTML).text

    requestBS = BeautifulSoup(requestLink.encode('ascii'), 'xml').feed
    stock_entry = [ 
        requestBS.find('entry').content.find('filing-href').getText(),
        requestBS.find('entry').content.find('filing-type').getText(),
        requestBS.find('entry').content.find('filing-date').getText() 
    ]
    # We get raw data link
    file_url = stock_entry[0].replace('-index.htm', '.txt')\
                            .replace('.txtl', '.txt')
    return stock_entry[2], file_url

def clean_up(text):
    from bs4 import BeautifulSoup # Web scrape
    import re # Web scrape
    import string
    # Removing HTML Tags and text to lower case
    text = BeautifulSoup(text, 'html.parser').get_text()
    text = text.lower()
    text = re.sub('\s+', ' ', text)
    """
        Remove digits from string
        Apparently using str.translate is faster than re.
    """
    # Removing all digits
    removal = str.maketrans(dict.fromkeys('0123456789'))
    # Removing all punctuations
    text = text.translate(removal)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

def getSentiment():
    import pandas as pd
    lm_df = pd.read_csv('loughran_mcdonald_master_dic_2016.csv')
    foo_list = ['Negative', 'Positive', 'Uncertainty', 'Litigious', \
                'Constraining', 'Interesting']
    lm_df = lm_df[foo_list + ['Word']]
    lm_df[foo_list] = lm_df[foo_list].astype(bool)
    lm_df = lm_df[(lm_df[foo_list]). any(1)]

    #Apply the same preprocessing to these words
    lm_df['Word'] = lemmatize_words(lm_df['Word'].str.lower())
    lm_df = lm_df.drop_duplicates('Word')
    return lm_df

def lemmatize_words(words):
    import nltk
    from nltk.stem import WordNetLemmatizer
    """
    Lemmatizing then tokenize the string to words.
    Parameters
    ----------
    words : list of tokens

    Returns
    -------
    lemmatized_words : list of str
        List of lemmatized words
    """
    lemmatized_words = []
    for w in words:
         lemmatized_words.append(WordNetLemmatizer().lemmatize(w))  
    
    return lemmatized_words

def get_bag_of_words(sentiment_words, docs):
    import pandas as pd
    from sklearn.feature_extraction.text import CountVectorizer
    import numpy as np
    vec = CountVectorizer(stop_words='english',vocabulary=sentiment_words)

    vectors = vec.fit_transform(docs)
    words_list = vec.get_feature_names() # all words that has results
    freq = np.ravel(vectors.sum(axis=0)) # total count of each word
    df = pd.DataFrame(list(zip(words_list, freq)), \
                     columns=['Word', 'Count'])
    return df


def nlpAnalysis(fHTML):
    import requests
    """
    Single File analysis.
    """
    # single file content get
    raw_file = requests.get(fHTML).text
    # Get cleaned up text without digits and html tags.
    text = clean_up(raw_file)
    # use of re.compile will split words faster in a sentence
    import re
    splitting = re.compile('\w+')
    lemma_text = lemmatize_words(splitting.findall(text))

    # stop words are not needed
    lm_df = getSentiment()

    # Get bag of words based on sentiment
    l = {}
    foo_list = ['Negative', 'Positive', 'Uncertainty', 'Litigious', 'Constraining', 'Interesting']

    for sentiment in foo_list:
        l.update({sentiment:get_bag_of_words(lm_df[lm_df[sentiment]]['Word'], lemma_text)})

    return l
