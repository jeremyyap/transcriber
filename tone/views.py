from django.shortcuts import render
from .models import Transcription, Subject, Audio

from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.template import RequestContext, loader
from django.conf import settings

import csv
import re

from Crypto.PublicKey import RSA
from base64 import b64decode

def transcribe(request, subjectId, questionId):

	subject = Subject.objects.get(pk=subjectId)
	audioId = subject.question_order.split(',')[int(questionId) - 1]

	if request.method == 'POST':
		result = request.POST.get('result', '')
		timeTaken = request.POST.get('timeTaken', '')

		audio = Audio.objects.get(pk=audioId)

		score = 0
		for c, a in zip(result, audio.answer):
			if c == a:
				score += 1

		Transcription.objects.create(subject=subject, audio=audio,
			result=result, timeTaken=timeTaken, score=score)

		if int(questionId) == 3:
			return HttpResponseRedirect('/tone/end')
		else:
			return HttpResponseRedirect('/tone/' + subjectId + '/' + str(int(questionId) + 1))

	else:
		alignments_file_path = settings.STATIC_ROOT + '/data/alignments/' + audioId + '.json'
		alignments = open(alignments_file_path, 'r').read()
		context = {
			'audio_file_path': 'data/audio/' + audioId + '.wav',
			'subject_id': subjectId,
			'question_id': questionId,
			'alignments': alignments,
		}
		return render(request, 'toneNumber.html', context)

def start(request):

	return render(request, 'start.html')

def survey(request):

	if request.method == 'POST':
		cipherName = request.POST.get('encryptedName', '')
		cipherEmail = request.POST.get('encryptedEmail', '')
		dominantLanguage = request.POST.get('dominantLanguage', '')
		otherLanguages = request.POST.get('otherLanguages', '')
		targetLanguage = request.POST.get('targetLanguage', '') == 'on'
		gender = request.POST.get('gender', '')
		age = request.POST.get('age', '')

		f = open(settings.STATIC_ROOT + '/rsa/private_key.pem', 'r')
		key = RSA.importKey(f.read())
		name = key.decrypt(b64decode(cipherName))
		email = key.decrypt(b64decode(cipherEmail))
		name = name.decode('utf-8').replace('\0', '').encode('utf-8')
		email = email.decode('utf-8').replace('\0', '').encode('utf-8')

		sub = Subject.objects.create(name=name, email=email, dominant_language=dominantLanguage,
			other_languages=otherLanguages, target_language=targetLanguage, gender=gender, age=age)

		# Generate questions for subject

		q3 = 2 + Subject.objects.filter(dominant_language=dominantLanguage).count()

		if sub.pk % 2 == 0:
			questionOrder = "1,2," + str(q3)
		else:
			questionOrder = "2,1," + str(q3)

		sub.question_order = questionOrder
		sub.save();

		return HttpResponseRedirect('/tone/' + str(sub.pk) + '/1')

	else:
		defaultLanguages = ['English', 'Mandarin']
		languages = Subject.objects.values_list('dominant_language', flat=True).distinct()
		languageSet = set(languages)
		languageSet.discard("Testing")
		languages = list(set(defaultLanguages) | languageSet)
		context = {
			'DLs': languages
		}
		return render(request, 'survey.html', context)

def end(request):

	return render(request, 'end.html')

def summary(request):
	entries = []
	for sub in Subject.objects.all():
		score = 0
		total = 0
		time = 0
		for t in Transcription.objects.filter(subject=sub):
			score += t.score
			total += t.audio.numSegments
			time += t.timeTaken

		if total == 0:
			continue

		entries.append({
			'subject': sub,
			'score': str(int(score / float(total) * 100)) + '%',
			'time': time,
		})
	entries = sorted(entries, key=lambda k: k['score'], reverse=True) 

	context = {
		'entries': entries
	}

	return render(request, 'summary.html', context)