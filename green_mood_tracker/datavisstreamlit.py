from green_mood_tracker.encoders import RobertaEncoder
from transformers import TFRobertaForSequenceClassification
import tensorflow as tf
import numpy as np
import pandas as pd
import altair as alt
from vega_datasets import data
import plotly.express as px
import plotly as py
import plotly.graph_objects as go
import pickle
from green_mood_tracker.data import clean
from geojson_rewind import rewind
import json
model_load = TFRobertaForSequenceClassification.from_pretrained('models/model_roBERTa_test_distil')
def cleantopic(df,topic="['solar', 'energy']"):
	df_topic = df[df['search'] == topic]
	print(df_topic[['tweet', 'search']])
	df_clean = clean(df_topic,'tweet')
	ds_twint_encoded = RobertaEncoder(batch_size=64).transform(df_clean.tweet, df_clean.timezone, shuffle=True)
	return ds_twint_encoded, df_clean
def results(ds_twint_encoded, df_clean):
	submission_pre = tf.nn.softmax(model_load.predict(ds_twint_encoded).logits)
	submission_pre = np.reshape(submission_pre.numpy(),(len(df_clean),2))
	return submission_pre
def comment_dataframe_prep(df_clean, submission_pre):
	comment_dataframe = df_clean.copy()
	comment_dataframe['nlikes'] = comment_dataframe['nlikes'].copy() + 1
	comment_dataframe['prob_neg'] = 0
	comment_dataframe['prob_pos'] = 0
	comment_dataframe['prob_neg'] = submission_pre[:,0]
	comment_dataframe['prob_pos'] = submission_pre[:,1]
	comment_dataframe['label'] = comment_dataframe['prob_pos'].apply((lambda x: 2 if x >= 0.55 else (0 if x <= 0.45 else 1)))
	comment_dataframe = comment_dataframe.drop_duplicates(subset=['id'],keep='first')
	comment_dataframe = comment_dataframe.drop_duplicates(subset=['date'],keep='first')
	comment_dataframe = comment_dataframe[comment_dataframe['date'] != '14502749']
	comment_dataframe['date'] = comment_dataframe[['date']].apply(pd.to_datetime)
	return comment_dataframe[['date','tweet','nlikes','label','prob_neg','prob_pos','state_code']]
def cumulative_features(comment_dataframe):
	cum_plot_df = comment_dataframe.sort_values(by='date')
	cum_plot_df['nlikes'] = cum_plot_df['nlikes'].copy() + 1
	cum_plot_df['neg_count'] = (cum_plot_df['label'] == 0).cumsum()
	cum_plot_df['pos_count'] = (cum_plot_df['label'] == 2).cumsum()
	cum_plot_df['neut_count'] = (cum_plot_df['label'] == 1).cumsum()
	cum_plot_df['neg-per'] = cum_plot_df.apply(lambda x: (x['neg_count']/(x['neg_count']+x['pos_count']+x['neut_count']))*100, axis=1)
	cum_plot_df['pos-per'] = cum_plot_df.apply(lambda x: (x['pos_count']/(x['neg_count']+x['pos_count']+x['neut_count']))*100, axis=1)
	cum_plot_df['neut-per'] = cum_plot_df.apply(lambda x: (x['neut_count']/(x['neg_count']+x['pos_count']+x['neut_count']))*100, axis=1)
	cum_plot_df['sentiment'] = cum_plot_df['label'].map({0:'Negative',1:'Neutral',2:'Positive'})
	cum_plot_df['pos_like_cum'] = (cum_plot_df['label'] == 2)*cum_plot_df['nlikes']
	cum_plot_df['neg_like_cum'] = (cum_plot_df['label'] == 0)*cum_plot_df['nlikes']
	cum_plot_df['neut_like_cum'] = (cum_plot_df['label'] == 1)*cum_plot_df['nlikes']
	cum_plot_df['pos_like_cum'] = cum_plot_df['pos_like_cum'].cumsum(skipna=True)
	cum_plot_df['neg_like_cum'] = cum_plot_df['neg_like_cum'].cumsum(skipna=True)
	cum_plot_df['neut_like_cum'] = cum_plot_df['neut_like_cum'].cumsum(skipna=True)
	cum_plot_df['neg_like-per'] = cum_plot_df.apply(lambda x: (x['neg_like_cum']/(x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']))*100 if (x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']) != 0 else 0. , axis=1)
	cum_plot_df['pos_like-per'] = cum_plot_df.apply(lambda x: (x['pos_like_cum']/(x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']))*100 if (x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']) != 0 else 0. , axis=1)
	cum_plot_df['neut_like-per'] = cum_plot_df.apply(lambda x: (x['neut_like_cum']/(x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']))*100 if (x['neg_like_cum']+x['pos_like_cum']+x['neut_like_cum']) != 0 else 0. , axis=1)
	return cum_plot_df
def polarity_calc(df_segmented_year):
	df_segmented_year['count'] = 1
	plotly_df = df_segmented_year.copy().groupby('state_code').agg({'prob_neg': 'sum','prob_pos': 'sum','count':'count'}).reset_index()
	plotly_df['polarity_av'] = plotly_df.copy().apply(lambda x: (x['prob_pos']-x['prob_neg'])/x['count'], axis=1)
	return plotly_df
#cum_plot_df = cumulative_features(comment_dataframe)
def altair_data(cum_plot_df):
	neg_like = cum_plot_df[['date','month','neg_like-per','sentiment']].rename(columns={'date':'date','neg_like-per':'Percentage of Likes Per Sentiment','sentiment':'sentiment', 'month':'month'})
	neg_like['sentiment'] = 'Negative'
	neg_like_last = neg_like.tail(1)
	pos_like = cum_plot_df[['date','month','pos_like-per','sentiment']].rename(columns={'date':'date','pos_like-per':'Percentage of Likes Per Sentiment','sentiment':'sentiment', 'month':'month'})
	pos_like['sentiment'] = 'Positive'
	pos_like_last = pos_like.tail(1)
	neut_like = cum_plot_df[['date','month','neut_like-per','sentiment']].rename(columns={'date':'date','neut_like-per':'Percentage of Likes Per Sentiment','sentiment':'sentiment', 'month':'month'})
	neut_like['sentiment'] = 'Neutral'
	neut_like_last = neut_like.tail(1)
	altrair_like_sum = pd.concat([neg_like_last,pos_like_last,neut_like_last],axis=0)
	#altrair_like_sum = altrair_like_sum.sort_values(by='date')
	neg = cum_plot_df[['date','neg-per','sentiment','month']].rename(columns={'date':'date','neg-per':'Percentage of Sentiment','sentiment':'sentiment', 'month':'month'})
	neg['sentiment'] = 'Negative'
	neg_last = neg.tail(1)
	pos = cum_plot_df[['date','pos-per','sentiment','month']].rename(columns={'date':'date','pos-per':'Percentage of Sentiment','sentiment':'sentiment', 'month':'month'})
	pos['sentiment'] = 'Positive'
	pos_last = pos.tail(1)
	neut = cum_plot_df[['date','neut-per','sentiment','month']].rename(columns={'date':'date','neut-per':'Percentage of Sentiment','sentiment':'sentiment', 'month':'month'})
	neut['sentiment'] = 'Neutral'
	neut_last = neut.tail(1)
	altrair_sent_sum = pd.concat([neg_last,pos_last,neut_last],axis=0)
	#altrair_sent_sum = altrair_sent_sum.sort_values(by='date')
	return altrair_like_sum,  altrair_sent_sum


def plot_map(cum_plot_df, country='US'):
	cum_plot_df['year'] = pd.DatetimeIndex(cum_plot_df['date']).year
	cum_plot_df['month'] = pd.DatetimeIndex(cum_plot_df['date']).month
	cum_plot_df['state_code'] = cum_plot_df['state_code'].replace({"East of England":"East","Yorkshire":"Yorkshire and the Humber",})
	if country == "UK":
		with open('green_mood_tracker/raw_data/uk_regions.geojson') as f:
			data = json.load(f)

		data_wind = rewind(data, rfc7946=False)

	# your color-scale
	scl = [[0.0, '#800000'],[0.25, '#ff0000'],[0.5, '#ffa500'],
	[0.75, '#00FF00'],[1.0, '#008000']] # purples

	data_slider = []
	figs_uk=[]
	altair_sent_by_year = []
	altair_like_by_year = []
	for year in cum_plot_df['year'].unique():
		df_segmented_year =  cum_plot_df[(cum_plot_df['year'] == year)]
		df_segmented = polarity_calc(df_segmented_year)
		altrair_sent_final = pd.DataFrame(columns = ['date','Percentage of Sentiment','sentiment','month'])
		altrair_like_final = pd.DataFrame(columns = ['date','Percentage of Likes Per Sentiment','sentiment','month'])
		for month in df_segmented_year['month'].unique():
			df_segmented_month =  df_segmented_year[(cum_plot_df['month'] == month)]
			df_segmented_month_cumulative = cumulative_features(df_segmented_month)
			altrair_like_sum,  altrair_sent_sum = altair_data( df_segmented_month_cumulative)
			altrair_sent_final = pd.concat([ altrair_sent_final,altrair_sent_sum],axis=0)
			altrair_like_final = pd.concat([ altrair_like_final,altrair_like_sum],axis=0)
		altrair_sent_final = altrair_sent_final.sort_values(by='month')
		altrair_like_final = altrair_like_final.sort_values(by='month')
		altair_sent_by_year.append(altrair_sent_final)
		altair_like_by_year.append(altrair_like_final)
		# df_segmented = df_segmented_year_cumulative.groupby('state_code').last()[['year','pos-per']].reset_index()


		if country == 'US':
			for col in df_segmented.columns:
				df_segmented[col] = df_segmented[col].astype(str)
			data_each_yr = dict(
								type='choropleth',
								locations = df_segmented['state_code'],
								z=df_segmented['polarity_av'].astype(float),
								locationmode='USA-states',
								colorscale = scl,
								zmin=-1,
								zmax=1,
								colorbar= {'title':'Positive sentiment Percentage'})

			data_slider.append(data_each_yr)
		elif country == 'UK':
			fig_2 = px.choropleth(df_segmented, geojson=data_wind, color='polarity_av',
					locations='state_code', featureidkey="properties.rgn19nm",
					projection="mercator",
					scope='europe',
					range_color = [1,-1],
					#color_continuous_scale=px.colors.sequential.Plasma
					color_continuous_scale = scl
				   )
			fig_2.update_geos(fitbounds="locations", visible=False)
			figs_uk.append(fig_2)

	#steps = []
	#for i in range(len(data_slider)):
		#step = dict(method='restyle',
					#args=['visible', [False] * len(data_slider)],
					#label='Year {}'.format(i + 2010))
		#step['args'][1][i] = True
		#steps.append(step)
	#sliders = [dict(active=0, pad={"t": 1}, steps=steps)]
	if country == 'US':
		layout = dict(geo=dict(scope='usa',
							   projection={'type': 'albers usa'}),
					  )
		return altair_sent_by_year, altair_like_by_year, layout, data_slider

	elif country == 'UK':
		return altair_sent_by_year, altair_like_by_year, figs_uk


	#print(data_slider)
	#fig = go.Figure(data=st_year, layout=layout)

	#fig.show()
def altair_plot_like(altair_like_by_year,year):
	source =  altair_like_by_year[abs(year-2020)]
	alt.data_transformers.disable_max_rows()
	fig_alt = alt.Chart(source).mark_area().encode(
	x="date:T",
	y="Percentage of Likes Per Sentiment:Q",
	color=alt.Color("sentiment:N", scale=alt.Scale(domain=['Negative', 'Neutral', 'Positive'],
            range=['#800000', '#FFA500', '#008000'])),
	tooltip = [alt.Tooltip("date:T"),
			   alt.Tooltip("Percentage of Likes Per Sentiment:Q"),
			   alt.Tooltip("sentiment:N")
			  ])
	return fig_alt
def altair_plot_tweet(altair_sent_by_year,year):
	source =  altair_sent_by_year[abs(year-2020)]
	alt.data_transformers.disable_max_rows()
	fig_alt = alt.Chart(source).mark_area().encode(
	x="date:T",
	y="Percentage of Sentiment:Q",

	color=alt.Color("sentiment:N", scale=alt.Scale(domain=['Negative', 'Neutral', 'Positive'],
            range=['#800000', '#FFA500', '#008000'])),

	tooltip = [alt.Tooltip("date:T"),
			   alt.Tooltip("Percentage of Sentiment:Q"),
			   alt.Tooltip("sentiment:N")
			  ])
	return fig_alt




#def altair_pie_tweet(altair_sent_by_year,year):


#	source =  altair_sent_by_year[abs(year-2020)]
#	alt.data_transformers.disable_max_rows()
#fig_pie = px.pie(source,
	#values='Percentage of Likes Per Sentiment', names='sentiment',
	#color_discrete_sequence=px.colors.sequential.algae)


#	colors = ['gold', 'mediumturquoise', 'darkorange', 'lightgreen']


#	fig_pie = go.Figure(data=[go.Pie(data =source).mark_area().encode(
#	x="date:T",
#	y="Percentage of Sentiment:Q",
#	color=alt.Color("sentiment:N", scale=alt.Scale(scheme='yellowgreen')),
#	tooltip = [alt.Tooltip("Date:T"),
#			   alt.Tooltip("Percentage of Sentiment (%):Q"),
#			   alt.Tooltip("Sentiment:N")
#			  ])])
#fig_pie.update_traces(hoverinfo='label+percent', textinfo='value', textfont_size=20,

					 #marker=dict(colors=colors, line=dict(color='#000000', width=2))
#	return fig_pie


def all_plotting(topic="['solar', 'energy']"):
	#us_twint = pd.read_csv('green_mood_tracker/raw_data/twint_US.csv',dtype={"date": "string", "tweet": "string"})
	uk_twint = pd.read_csv('green_mood_tracker/raw_data/twint_data_UK.csv',dtype={"nlikes":"float64"})

	topics = ["['energy', 'bills']","['solar', 'power']", "['nuclear', 'power']", "['wind', 'power']"]

	for topic in topics:
		ds_twint_encoded, df_clean = cleantopic(uk_twint, topic)
		submission_pre = results(ds_twint_encoded, df_clean)

		comment_dataframe = comment_dataframe_prep(df_clean, submission_pre)
		comment_dataframe.to_csv(f"green_mood_tracker/raw_data/{topic}.csv")
if __name__ == "__main__":
	#df = read_data()
	all_plotting(topic="['solar', 'energy']")
