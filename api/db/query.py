import os
import json
import uuid
import random
import datetime
import exifread
#import ConfigParser
import configparser
from sqlalchemy import func
from sqlalchemy import and_
from sqlalchemy import tuple_
import sqlalchemy
from ..utils.checksum import comp_checksum
from ..strings.auto_complete import AutoComplete
from .DB import DBManager, DBAddPhoto, InitPhotosDb, DumpTables, PhotoModel, LabelModel, UserModel, PhotoSizeModel, PhotoBlurModel, TopicModel
from ..filters.filtering import GetImageDimensions

CONFIG_FILE="/etc/api.cfg"

def GetHostIP(cfg_file=CONFIG_FILE):
	config = configparser.ConfigParser()
	config.read(cfg_file)
	return config.get("host", "ipv4")

def GetImageDir(cfg_file=CONFIG_FILE):
	config = configparser.ConfigParser()
	config.read(cfg_file)
	return config.get("dir", "path")

def GetMediumScaledImageDir(cfg_file=CONFIG_FILE):
	config = configparser.ConfigParser()
	config.read(cfg_file)
	return config.get("m_dir", "path")

def GetThumbnailImageDir(cfg_file=CONFIG_FILE):
	config = configparser.ConfigParser()
	config.read(cfg_file)
	return config.get("s_dir", "path")

def GetEnhancedImageDir(cfg_file=CONFIG_FILE):
	config = configparser.ConfigParser()
	config.read(cfg_file)
	return config.get("e_dir", "path")

def GetDateTime2(imagePath):
	fp = open(imagePath, 'rb')
	tags = exifread.process_file(fp)
	fp.close()
	dateinfo = str(tags['EXIF DateTimeOriginal'])
	dateinfo = dateinfo.split(' ')
	yymmdd = dateinfo[0].replace(':', ' ')
	return [int(s) for s in yymmdd.split(' ')]

def GetDateTime(imagePath):
	fp = open(imagePath, 'rb')
	tags = exifread.process_file(fp)
	fp.close()
	dateinfo = str(tags['EXIF DateTimeOriginal'])
	dateinfo = dateinfo.split(' ')
	yymmdd = dateinfo[0].replace(':', ' ')
	timeinfo = dateinfo[1].replace(':', ' ')
	timeinfo = [int(s) for s in timeinfo.split(' ')]
	secs = timeinfo[0] * 3600 + timeinfo[1] * 60 + timeinfo[2]
	return [ [int(s) for s in yymmdd.split(' ')], secs ]

def GetDateTimeLocal():
	now = datetime.datetime.now()
	year = now.year
	month = now.month
	day = now.day
	return [year, month, day, 0]

def GetPath(img_uuid):
	img_dir = GetImageDir(CONFIG_FILE)
	imgPath = '{}/{}.JPG'.format(img_dir, img_uuid)
	return imgPath

def GetEnhancedImagePath(img_uuid):
	img_dir = GetEnhancedImageDir(CONFIG_FILE)
	imgPath = '{}/{}_e.JPG'.format(img_dir, img_uuid)
	return imgPath

def ConvertAlbumNameToID(album_name):
	return comp_checksum([album_name])

def SortbyDate(jsonData):
	year  = int(jsonData["value"]["year"])
	month = int(jsonData["value"]["month"])
	day   = int(jsonData["value"]["day"])
	dt = datetime.date(year=year, month=month, day=day)
	return dt

def LookupPhotos(user_name, like=False):
	photoPaths = []
	with DBManager() as db:
		_dbSession = db.getSession()
		if like:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter((PhotoModel.Likes == "Like")).order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).order_by(
						PhotoModel.DayTime
						)
		else:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).order_by(
						PhotoModel.DayTime
						)
		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}-{}'.format(photo.DayTime, photo.Day, photo.Month,
			photo.Year), "name" : photo.Name, "tags" : photo.Tags }})
	return photoPaths

def LookupPhotosByDate(user_name, year, month, day=None):
	photoPaths = []
	with DBManager() as db:
		_dbSession = db.getSession()
		if day:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(and_(PhotoModel.Year == year, PhotoModel.Month == month, PhotoModel.Day == day)).all()
		else:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(and_(PhotoModel.Year == year, PhotoModel.Month == month)).all()
		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}'.format(photo.Day, photo.Month,
			photo.Year), "name" : photo.Name, "tags" : photo.Tags }})
	return photoPaths

def GetAlbumPhotos(user_name, album, blur=0, year=0):
	photoPaths = []
	result = []

	with DBManager() as db:
		_dbSession = db.getSession()
		if year == 0:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(PhotoModel.Tags == album) \
						.order_by(
						PhotoModel.Year
						).order_by(
						PhotoModel.Month
						).order_by(
						PhotoModel.Day
						).order_by(
						PhotoModel.DayTime
						)
		else:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(PhotoModel.Tags == album).filter(PhotoModel.Year==year) \
						.order_by(
						PhotoModel.Month
						).order_by(
						PhotoModel.Day
						).order_by(
						PhotoModel.DayTime
						)

		for photo in result:
			if DBGetPhotoBlur(photo.UUID) >= blur:
				w, h = DBGetPhotoDimensions(photo.UUID)
				photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}-{}'.format(photo.DayTime, photo.Day, photo.Month, \
					photo.Year), "name" : photo.Name, "tags" : photo.Tags , "like" : photo.Likes, "width" : w, "height" :h }})
			#photoPaths.append(photo.UUID)
		return photoPaths

def GetAlbumPhotosOnlyLiked(user_name, album):
	photoPaths = []
	result = []

	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(PhotoModel.Tags == album).filter((PhotoModel.Likes == "Like")) \
						.order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).order_by(
						PhotoModel.DayTime
						)

		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}-{}'.format(photo.DayTime, photo.Day, photo.Month, \
				photo.Year), "name" : photo.Name, "tags" : photo.Tags , "like" : photo.Likes }})
			#photoPaths.append(photo.UUID)
		return photoPaths

def GetAlbumDates(user_name, album):
	dt = ""
	result = []

	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(PhotoModel.Tags==album) \
						.order_by(
						PhotoModel.Year
						).order_by(
						PhotoModel.Month
						).order_by(
						PhotoModel.Day
						).order_by(
						PhotoModel.DayTime
						).all()

		if len(result) > 0:
			photo1 = result[0]
			start = '{}/{}/{}'.format(photo1.Month, photo1.Day, photo1.Year)
			photo2 = result[len(result) - 1]
			end =  '{}/{}/{}'.format(photo2.Month, photo2.Day, photo2.Year)
			dt = '{}-{}'.format(start, end)
		return dt

def FilterPhotos(user_name, start_year, to_year, album=None):
	photoPaths = []
	result = []

	#check unicode
	if not isinstance(start_year, int) and not start_year.isnumeric():
		start_year = 0

	if not isinstance(to_year, int) and not to_year.isnumeric():
		to_year = 2050

	with DBManager() as db:
		_dbSession = db.getSession()
		if album:
			search = "%{}%".format(album)
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(PhotoModel.Tags.ilike(search)) \
						.order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).order_by(
						PhotoModel.DayTime
						)
			result = [ photo for photo in result if photo.Year >= int(start_year) and \
				photo.Year <= int(to_year) ]
		else:
			result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter(and_(PhotoModel.Year >= int(start_year),
						 PhotoModel.Year <= int(to_year))) \
						.order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).order_by(
						PhotoModel.DayTime
						)

		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}-{}'.format(photo.DayTime, photo.Day, photo.Month, \
				photo.Year), "name" : photo.Name, "tags" : photo.Tags }})
			#photoPaths.append(photo.UUID)

	return photoPaths

def FilterPhotosPotraitStyle(user_name, start_year, to_year, standard_sizes, album=None):
	photos = []
	result = FilterPhotos(user_name, start_year, to_year, album)
	for photo in result:
		w, h = DBGetPhotoDimensions(photo["value"]["uuid"])
		if (w, h) not in standard_sizes:
			continue
		photo["value"]["width"] = int(w)
		photo["value"]["height"] = int(h)
		photos.append(photo)
		#print (photo)
	return photos

def FilterLabeledPhotos(user_name, object_name, skip=False):
	photoPaths = []

	with DBManager() as db:
		_dbSession = db.getSession()
		if skip:
			result = _dbSession.query(PhotoModel)\
				.join(LabelModel, PhotoModel.UUID==LabelModel.UUID)\
				.filter(~LabelModel.Labels.contains(object_name)).filter(PhotoModel.Username==user_name).all()
		else:
			result = _dbSession.query(PhotoModel)\
				.join(LabelModel, PhotoModel.UUID==LabelModel.UUID)\
				.filter(LabelModel.Labels.contains(object_name)).filter(PhotoModel.Username==user_name).all()
		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "date" : '{}-{}-{}-{}'.format(photo.DayTime, photo.Day, photo.Month, \
				photo.Year), "name" : photo.Name, "tags" : photo.Tags }})
			#photoPaths.append(photo.UUID)
	return photoPaths

def FilterLabeledPhotosPotraitStyle(user_name, object_name, standard_sizes, skip=False):
	photos = []
	result = FilterLabeledPhotos(user_name, object_name, skip)
	for photo in result:
		w, h = DBGetPhotoDimensions(photo["value"]["uuid"])
		#print (w, h, standard_sizes)
		if (w, h) not in standard_sizes:
			continue
		photo["value"]["width"] = int(w)
		photo["value"]["height"] = int(h)
		photos.append(photo)
		#print (photo)
	return photos

def GetAlbumViewItems(user_name):
	photoPaths = {}
	photoList = []
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel)\
				.join(PhotoSizeModel, PhotoModel.UUID==PhotoSizeModel.UUID)\
				.filter(PhotoModel.Username==user_name)\
				.filter(PhotoSizeModel.Width>PhotoSizeModel.Height)\
				.filter(PhotoSizeModel.Width <= 6016)\
				.order_by(PhotoSizeModel.Width.desc()).all()

	for photo in result:
		if photo.Tags not in photoPaths:
			photoPaths[photo.Tags] =\
				{ \
					"value" : \
						{	"uuid"  : photo.UUID, \
							"daytime" : photo.DayTime, \
							"day"   : photo.Day, \
							"month" : photo.Month, \
							"year"  : photo.Year, \
							"name"  : photo.Name, \
							"tags"  : photo.Tags, \
							"count" : int(1) \
						} \
				}
		else:
			photoPaths[photo.Tags]["value"]["count"] += 1

	for photo in photoPaths:
		photoList.append(photoPaths[photo])
	photoList.sort(key=SortbyDate, reverse=True)
	return photoList

def GetNumAlbums(user_name):
	with DBManager() as db:
		_dbSession = db.getSession()
		return _dbSession.query(PhotoModel.Tags).filter(PhotoModel.Username==user_name).distinct(PhotoModel.Tags).count()
	return 0

def FilterPhotoAlbums(user_name):
	#deprecated
	photoPaths = {}
	photoList = []
	result = []
	'''
	select sub.Tags, max(sub.width)
		from (select p.Tags, p.UUID, s.width, s.height from PhotoTable p inner join
		PhotoSizeTable s on p.UUID = s.UUID where p.username = "saptarshi.mrg@gmail.com"
		and s.width > s.height order by p.Tags) sub group by sub.Tags;
	'''
	with DBManager() as db:
		_dbSession = db.getSession()
		subq = _dbSession.query(PhotoModel.Tags, sqlalchemy.func.max(PhotoSizeModel.Width).label('max_width'))\
				.join(PhotoSizeModel, PhotoModel.UUID==PhotoSizeModel.UUID)\
				.filter(PhotoModel.Username==user_name)\
				.filter(PhotoSizeModel.Width>PhotoSizeModel.Height)\
				.group_by(PhotoModel.Tags).subquery()
		#https://stackoverflow.com/questions/30311354/sqlalchemy-joining-with-subquery-issue
		result = _dbSession.query(PhotoModel)\
				.join(PhotoSizeModel, PhotoModel.UUID==PhotoSizeModel.UUID)\
				.filter(PhotoModel.Username==user_name)\
				.join(subq, PhotoModel.Tags == subq.c.Tags)\
				.filter(PhotoSizeModel.Width== subq.c.max_width).all()

	#random.shuffle(result)

	#unique albums
	for photo in result:
		# show only high resolution photos
		if photo.Tags not in photoPaths:
			photoPaths[photo.Tags] =\
				{ \
					"value" : \
						{	"uuid"  : photo.UUID, \
							"daytime" : photo.DayTime, \
							"day"   : photo.Day, \
							"month" : photo.Month, \
							"year"  : photo.Year, \
							"name"  : photo.Name, \
							"tags"  : photo.Tags, \
							"count" : int(0) \
						} \
				}

	with DBManager() as db:
		_dbSession = db.getSession()
		for key in photoPaths:
			photoPaths[key]["value"]["count"] = \
				 _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name)\
				 .filter(PhotoModel.Tags == key).count()
			photoList.append(photoPaths[key])

	photoList.sort(key=SortbyDate, reverse=True)
	return photoList

def TestDuplicate(user_name, sourceBlob, digest, sourcetag):
	with DBManager() as db:
		_dbSession = db.getSession()	
		result = _dbSession.query(PhotoModel).filter(PhotoModel.Username==user_name).filter((PhotoModel.Digest == digest)).all()
		for photo in result:
			imgPath = '{}/{}.JPG'.format(photo.NameSpace, photo.UUID)
			print (imgPath)
			with open(imgPath, 'rb') as fp:
				fileBlob = fp.read()
				if bytearray(sourceBlob) == bytearray(fileBlob):
					if sourcetag == photo.Tags:
						return True
	return False

def InsertPhoto(user_name, filename, fileBlob, description):
	img_dir = GetImageDir(CONFIG_FILE)
	img_uuid = uuid.uuid4()
	digest = comp_checksum(fileBlob)
	album_id = ConvertAlbumNameToID(description)

	if TestDuplicate(user_name, fileBlob, digest, description):
		print ("Detected duplicate entry")
		return;

	imgPath = '{}/{}.JPG'.format(img_dir, img_uuid)
	print('InsertPhoto imgPath :{}'.format(imgPath))
	fd = os.open(imgPath, os.O_RDWR | os.O_CREAT, 0o644)
	os.write(fd, fileBlob)
	os.close(fd)
	try:
		[[year, month, day], secs] = GetDateTime(imgPath)
	except:
		[year, month, day, secs] = GetDateTimeLocal()

	with DBManager() as db:
		_dbSession = db.getSession()
		DBAddPhoto(_dbSession, img_uuid, album_id, user_name, filename, digest, \
			year, month, day, secs, img_dir, " ", description)
		_dbSession.commit()
	print ('{} saved to disk'.format(filename))

def MarkPhotoFav(img_uuid, like=True):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for i in result:
			if like:
				i.Likes = "Like"
			else:
				i.Likes = "Unlike"
			_dbSession.commit()
		print ("Marked Like photo :", img_uuid, like)

def DeletePhoto(img_uuid):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for i in result:
			_dbSession.delete(i)
		_dbSession.commit()

def UpdatePhotoTag(img_uuid, tag):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for i in result:
			i.Tags = tag
		_dbSession.commit()
		print ('Updated {} {}'.format(img_uuid, tag))

def GetPhotoAlbumID(img_uuid):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).first()
		return result.AlbumID
	return None

def AutoCompleteAlbum(user_name, text):
	tl = []
	with DBManager() as db:
		_dbSession = db.getSession()
		#for value in _dbSession.query(PhotoModel.Tags).filter(PhotoModel.Username==user_name).distinct():
		for value in _dbSession.query(PhotoModel.Tags).filter(PhotoModel.Username==user_name).distinct(PhotoModel.Tags):
			#tl.append(value[0].lower())
			print (value.Tags)
			tl.append(value.Tags.lower())
		#print (text, tl)
	return AutoComplete(tl, text)

def ScanPhotos():
	result = []
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).order_by(
						PhotoModel.Year.desc()
						).order_by(
						PhotoModel.Month.desc()
						).order_by(
						PhotoModel.Day.desc()
						).all()
		for i in result:
			print (i)

def GetScaledImage(img_uuid):
	img_data = None
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for r in result:
			if len(r.NameSpace_Medium) > 1:
				#imgPath = '{}{}_m.JPG'.format(result.NameSpace_Medium, result.UUID)
				imgPath = '{}{}_m.JPG'.format("/mnt/target/photos_small/", r.UUID)
				with open(imgPath, 'rb') as f:
					img_data = f.read()
	return img_data

def GetEnhancedImage(img_uuid):
	img_data = None
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for r in result:
				imgPath = '{}{}_e.JPG'.format("/mnt/target/photos_enhanced/", r.UUID)
				if os.path.exists(imgPath):
					with open(imgPath, 'rb') as f:
						img_data = f.read()
	return img_data

def GetThumbnailImage(img_uuid):
	img_data = None
	'''
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(PhotoModel).filter((PhotoModel.UUID == img_uuid)).all()
		for r in result:
			if len(r.NameSpace_Medium) > 1:
				#imgPath = '{}{}_m.JPG'.format(result.NameSpace_Medium, result.UUID)
				imgPath = '{}{}_m.JPG'.format("/mnt/target/photos_thumbnail/", r.UUID)
				with open(imgPath, 'rb') as f:
					img_data = f.read()
	'''
	return img_data

def DBGetPhotoLabel(imgUUID):
	"""
		fetch a row for the imgUUID
	"""
	entry = None
	with DBManager() as db:
		_dbSession = db.getSession()
		entry =  _dbSession.query(LabelModel).filter(LabelModel.UUID==imgUUID).first()
		return entry.Labels if entry else None

def DBAddPhotoLabel(imgUUID, imgLabels):
	"""
		insert record
	"""
	entry = LabelModel(UUID=imgUUID, Labels=imgLabels)
	with DBManager() as db:
		_dbSession = db.getSession()
		_dbSession.add(entry)
		_dbSession.commit()
		return entry


def DBGetUnLabeledPhotos():
	"""
		fetch imgUUIDs in PhotoTable not in LabelTable
	"""
	result = []
	with DBManager() as db:
		dbSession = db.getSession()
		entries = dbSession.query(PhotoModel)\
                    .outerjoin(LabelModel, PhotoModel.UUID == LabelModel.UUID)\
                    .filter(LabelModel.Labels == None).all()
		for entry in entries:
			result.append(entry.UUID)
	return result

def LookupUser(username, password):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(UserModel).filter(UserModel.Username==username).first()
		if result:
			return result.Password == password
		else:
			return False

def AddUser(username, password):
	user_uuid = uuid.uuid4()
	user = UserModel(UUID=user_uuid, Username=username, Password=password)
	with DBManager() as db:
		_dbSession = db.getSession()
		_dbSession.add(user)
		_dbSession.commit()
	return user

def DBGetUserImage(username):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(UserModel).filter(UserModel.Username==username).first()
		if result:
			return result.ImageUUID
		else:
			return False

def DBSetUserImage(username, image_uuid):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(UserModel).filter(UserModel.Username==username).first()
		if result:
			result.ImageUUID = image_uuid
			_dbSession.commit()
			#print ('Updated User image {}'.format(img_uuid))
		else:
			print ('invalid user name :{}'.format(username))
			return None

def DBGetUserGooglePhotosCredentials(username):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(UserModel).filter(UserModel.Username==username).first()
		if result:
			return (result.GooglePhotosClientId, result.GooglePhotosSecretKey)
		else:
			return None

def DBSetUserGooglePhotosCredentials(username, client_id, secret_key):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(UserModel).filter(UserModel.Username==username).first()
		if result:
			result.GooglePhotosClientId = client_id
			result.GooglePhotosSecretKey = secret_key
			_dbSession.commit()

def DBGetPhotoDimensions(imgUUID):
	"""
		fetch a row for the imgUUID
	"""
	entry = None
	with DBManager() as db:
		_dbSession = db.getSession()
		entry =  _dbSession.query(PhotoSizeModel).filter(PhotoSizeModel.UUID==imgUUID).first()
		if entry:
			return entry.Width, entry.Height
		else:
			return 0, 0

def DBAddPhotoDimensions(imgUUID, width, height):
	"""
		insert record
	"""
	entry = PhotoSizeModel(UUID=imgUUID, Width=width, Height=height)
	with DBManager() as db:
		_dbSession = db.getSession()
		_dbSession.add(entry)
		_dbSession.commit()
	return entry

def DBGetPhotoNullDimensions():
	"""
		fetch imgUUIDs in PhotoTable not in LabelTable
	"""
	result = []
	with DBManager() as db:
		dbSession = db.getSession()
		entries = dbSession.query(PhotoModel)\
                    .outerjoin(PhotoSizeModel, PhotoModel.UUID == PhotoSizeModel.UUID)\
                    .filter(PhotoSizeModel.UUID == None).all()
		for entry in entries:
			result.append(entry.UUID)
	return result

def DBAddNewTopic(uuid, topic, input):
	"""
		publish new topic to PhotoTable
	"""
	[year, month, day, _] = GetDateTimeLocal()
	with DBManager() as db:
		entry = TopicModel(UUID=uuid, Topic=topic, JSONInput=input, JSONOutput="", \
			State=0, Day=day, Month=month, Year=year)
		_dbSession = db.getSession()
		_dbSession.add(entry)
		_dbSession.commit()
	return uuid

def DBGetNewTopics():
	result = []
	with DBManager() as db:
		dbSession = db.getSession()
		entries = dbSession.query(TopicModel)\
                    .filter(TopicModel.State < 2).all()
		for entry in entries:
			result.append(entry)
	return result


def DBUpdateTopic(uuid, topic, output, state):
	with DBManager() as db:
		dbSession = db.getSession()
		entry = dbSession.query(TopicModel)\
                    .filter(TopicModel.Topic==topic).filter(TopicModel.UUID == uuid).first()
		print (entry)
		entry.JSONOutput = output
		entry.State = state
		dbSession.commit()

def DBGetNextSyncTopic():
	tuuid = None
	json_input = None
	with DBManager() as db:
		dbSession = db.getSession()
		result = dbSession.query(TopicModel)\
					.filter(TopicModel.Topic == "GPhotos") \
                    .filter(TopicModel.State < 2).first()
		if result:
			tuuid = result.UUID
			json_input = json.loads(result.JSONInput)
	return tuuid, "GPhotos", json_input

def DBGetLastSyncTopic():
	tuuid = None
	json_input = None
	with DBManager() as db:
		dbSession = db.getSession()
		result = dbSession.query(TopicModel)\
					.filter(TopicModel.Topic == "GPhotos") \
                    .filter(TopicModel.State == 2).all()
		if result:
			result = [r for r in result]
			n = len(result)
			if n > 0:
				tuuid = result[n - 1].UUID
				json_input = json.loads(result[n-1].JSONInput)
	return tuuid, json_input


def DBDeleteSyncTopic(tuuid):
	with DBManager() as db:
		_dbSession = db.getSession()
		result = _dbSession.query(TopicModel).filter((PhotoModel.UUID == tuuid)).all()
		for i in result:
			_dbSession.delete(i)
		_dbSession.commit()

def DBGetSyncTopics():
	photoPaths = []
	with DBManager() as db:
		dbSession = db.getSession()
		result = dbSession.query(TopicModel)\
					.filter(TopicModel.Topic == "GPhotos").all()
		for photo in result:
			photoPaths.append({ "value" : { "uuid" : photo.UUID, "period" : photo.JSONInput, "result" : photo.JSONOutput}})
	return photoPaths

def DBGetPhotoBlur(imgUUID):
	"""
		fetch a row for the imgUUID
	"""
	entry = None
	with DBManager() as db:
		_dbSession = db.getSession()
		entry =  _dbSession.query(PhotoBlurModel).filter(PhotoBlurModel.UUID==imgUUID).first()
		if entry:
			return entry.Blur
		else:
			return 0

def DBAddPhotoBlur(imgUUID, blur):
	"""
		insert record
	"""
	entry = PhotoBlurModel(UUID=imgUUID, Blur=blur)
	with DBManager() as db:
		_dbSession = db.getSession()
		_dbSession.add(entry)
		_dbSession.commit()
	return entry