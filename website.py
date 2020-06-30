from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects import postgresql #Allows me to store cidr
#for ssl connection to heroku server
import os
import psycopg2
from newsapi import NewsApiClient
import logging
import sys
#Chart
from bokeh.models.annotations import Title
from pandas_datareader import data
from datetime import datetime, timedelta, timezone
from bokeh.plotting import figure, show, output_file
#Import embed tools for Flask website
from bokeh.embed import components, autoload_static
#Import content delivery network
from bokeh.resources import CDN
from bokeh.models.widgets import Panel, Tabs
from bokeh.io import output_file, show
from bokeh.plotting import figure, curdoc

#Machine Learning
from ml import readReturnLink, nlpAnalysis, clean_up, getSentiment
import nltk # Natural Language Toolkit
import numpy as np
import pickle 


#instantiating the flask class
app=Flask(__name__)

# Database Initialisation
app.config['SQLALCHEMY_DATABASE_URI']=os.getenv('DATABASE_URL')
# Uncomment below if using personal postgresql
# app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:pass@localhost/Visitor'
db = SQLAlchemy(app)
class Database(db.Model):
    __tablename__="Visitor"
    id=db.Column(db.Integer, primary_key=True)
    ticker_=db.Column(db.String(10))
    year_=db.Column(db.Integer)
    ip_add_ = db.Column(postgresql.CIDR)
    dt_ = db.Column(db.DateTime, default=(datetime.utcnow() + timedelta(hours=8)))

    def __init__(self, ticker_,year_, ip_add_, dt_):
        self.ticker_ = ticker_
        self.year_ = year_
        self.ip_add_ = ip_add_
        self.dt_ = dt_

# NewsApiClient
key = '822de28aa09e4918aacaa41fc31d7cb8'
newsapi = NewsApiClient(api_key=key)

# Function for stock chart calculation
def inc_dec(c,o):
            if c>o:
                value="Increase"
            elif c<o:
                value="Decrease"
            else:
                value="Equal"
            return value

@app.route('/')
def plot():
    return render_template("plot.html")

@app.route('/', methods=['GET', 'POST'])
def show():
    # Definitions
    symbol=''
    mlMsg=''
    docDate=''
    text = ""
    news = ""
    mlLink = ''
    disclaimer=""
    

    if request.method=='POST':
        symbol = request.form['symbol']
        year_in = int(request.form['year'])
        cidr = request.remote_addr
        dt_eg=None
        
        # Database set up connection
        db_row = Database(symbol, year_in, cidr, dt_eg)
        db.session.add(db_row)
        db.session.commit()
        
        start=datetime(year_in,1,1)
        end=datetime.today().strftime('%Y-%m-%d 00:00:00')
    
        #Set Title
        t = Title()
        t.text = ('$' + symbol.upper() + ' Candlestick Chart. (Try out the interactive toolbar on the right to zoom or save the plot as Image.)')

        p=figure(x_axis_type='datetime', width=1000, height=300,sizing_mode='scale_width')
        p.title=t
        #set transparency of grid lines.
        p.grid.grid_line_alpha=0.3

        empty_title = Title()
        empty_title.text = ('NLP')
        empty_bokeh = figure(x_axis_type='datetime', width=400, height=400)
        empty_bokeh.title = empty_title
        p1 = figure()
        p2 = figure()
        p3 = figure()
        p4 = figure()
        p5 = figure()
        p6 = figure()
        p7 = figure()

        hours = 12*60*60*1000
        # Get Stock Data
        try:
            #load data
            df= data.DataReader(name=symbol, data_source="yahoo", start=start,end=end)
        except ("UndefinedError",TypeError) as e:
            df= data.DataReader(name=symbol, data_source="yahoo", start=None, end=None)
            text = f"There is no data for year {year_in}. Displaying earliest possible date."

        # Charting
        try:
            df["Status"]=[inc_dec(c,o) for c,o in zip(df.Close, df.Open)]
            df["Middle"]=(df.Open+df.Close)/2
            df["Height"]=abs(df.Close-df.Open)

            p.segment(df.index, df.High, df.index, df.Low, color="Black")

            p.rect(df.index[df.Status=="Increase"], df.Middle[df.Status=="Increase"],
                    hours,df.Height[df.Status=="Increase"], fill_color="green", line_color="black")
            p.rect(df.index[df.Status=="Decrease"], df.Middle[df.Status=="Decrease"],
                    hours, df.Height[df.Status=="Decrease"], fill_color="red", line_color="black")
            s1,d1 = components(p)
            
            earliest_timestamp=df.index.min()

            if text =="":
                text = "From earliest possible date, " + earliest_timestamp.strftime('%Y-%m-%d') + " till " + datetime.strftime(datetime.now(), '%Y-%m-%d')
            else:
                text = f"Displaying earliest possible date. " + earliest_timestamp.strftime('%Y-%m-%d') + " till " + datetime.strftime(datetime.now(), '%Y-%m-%d')
        except:
            text = "Wrong ticker symbol or there is no data, please try again. "

        #NewsApi
        try:
            kw = '$' + symbol
            # NewsApi
            news = newsapi.get_everything(q=kw, language='en', from_param=(datetime.strftime(datetime.now(), '%Y-%m-%d')))['articles'][:10]
            foo_loop=1
            while len(news)<10:
                news1 = newsapi.get_everything(q=kw, language='en', from_param=(datetime.strftime(datetime.now() - timedelta(foo_loop), '%Y-%m-%d')))['articles'][:10]
                news.append(news1[(10-len(news))])
                foo_loop+=1
        except:
            s1,d1 = components(p)
            text = text + "Looks like NewsAPI is having error fetching data from source."

        # Machine Learning Portion
        try:
            
            docDate, mlHTML = readReturnLink(symbol)
            stockDict = nlpAnalysis(mlHTML)

            # NLP Chart
            b = stockDict['Negative'].sort_values('Count', ascending=False).iloc[:20]
            p1 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p1.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='red')
            tab1 = Panel(child=p1, title='Negative')


            b = stockDict['Positive'].sort_values('Count', ascending=False).iloc[:20]
            p2 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p2.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='green')
            tab2 = Panel(child=p2, title='Positive')

            b = stockDict['Uncertainty'].sort_values('Count', ascending=False).iloc[:20]
            p3 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p3.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='yellow')
            tab3 = Panel(child=p3, title='Uncertainty')

            b = stockDict['Litigious'].sort_values('Count', ascending=False).iloc[:20]
            p4 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p4.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='purple')
            tab4 = Panel(child=p4, title='Litigious')

            b = stockDict['Constraining'].sort_values('Count', ascending=False).iloc[:20]
            p5 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p5.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='navy')
            tab5 = Panel(child=p5, title='Constraining')

            b = stockDict['Interesting'].sort_values('Count', ascending=False).iloc[:20]
            p6 = figure(y_range=b['Word'].tolist(), plot_width=500, plot_height=400)
            p6.hbar(y=b['Word'].tolist(), right=b['Count'].tolist(), color='orange')
            tab6 = Panel(child=p6, title='Interesting')

            palette=[ 'red', 'green', 'yellow', 'purple', 'navy', 'orange']
            foobar={k:v['Count'].sum() for (k,v) in stockDict.items()}

            p7 = figure(x_range = list(foobar.keys()), plot_width=500, plot_height=400,)
            p7.vbar(x=list(foobar.keys()), top=list(foobar.values()), color=palette)
            tab7 = Panel(child=p7, title='Summary')      
                    
            tabs = Tabs(tabs=[tab7, tab1, tab2, tab3, tab4, tab5, tab6])
            s2, d2 = components(tabs)
            mlMsg = f"This is {symbol.upper()}'s 10-K Annual Report. Release Date: {docDate}."
            mlLink = mlHTML
            mlHeader= f"{'$' + symbol.upper()}'s 10-K Report's Overall Sentiments"
            disclaimer= "Credits to Loughran-McDonald sentiment lexicon, for financial documents. "

        except:
            s2, d2 = components(empty_bokeh)
            mlMsg = "Sorry, there are no 10-K document for this company or there is an error."
            mlHeader=""
    # symbol, year_in, docDate, mlHTML, stockDict.keys()
    headline = f"Top 10 Latest News for {'$' + symbol.upper()}"
    cdn_js=CDN.js_files[0]
    return render_template("plot.html", msg=text, s1=s1, d1=d1, s2=s2, d2=d2, news=news, cdn_js=cdn_js, mlMsg=mlMsg, mlLink=mlLink, headline=headline, mlHeader=mlHeader, disclaimer=disclaimer)

        
if __name__=="__main__":
    app.run(debug=True)
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.ERROR)