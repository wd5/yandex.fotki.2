# encoding=utf8
'''
Модели данных.
@author: Mic, 2012
'''

from dm_yf.protocol import Service

# Адрес сервисного документа:
SERVICE_URL = 'http://api-fotki.yandex.ru/api/me/'

class AlbumList(object):
    '''
    Список альбомов.
    '''
    
    @classmethod
    def get(cls):
        '''
        Фабрика списков альбомов.
        @return: AlbumList
        '''
        service = Service.get(SERVICE_URL)
        resource = service.get_resource('album-list')
        if resource is None:
            return None
        return cls(resource)
    
    def __init__(self, resource):
        '''
        @param resource: Resource
        '''
        self._albums = None
        self._resource = resource
        
    def _get_albums(self):
        '''
        Загружает список альбомов.
        @return: list
        '''
        albums = []
        resources = self._resource.get_resources('self')
        for resource in resources:
            album = Album(resource)
            albums.append(album)
        return albums
        
    def get_albums(self):
        '''
        Возвращает список альбомов.
        @return: string
        '''
        if self._albums is None:
            self._albums = self._get_albums()
        return self._albums


class Album(object):
    '''
    Альбом.
    '''
    
    def __init__(self, resource):
        '''
        @param resource: Resource
        '''
        self._photos = None
        self._resource = resource
        
    def __str__(self):
        return '<Album "%s">'%self.get_title()
        
    def get_title(self):
        '''
        Возвращает название альбома.
        @return: string
        '''
        return self._resource.get_property('title').encode('utf8')
    
    def _get_photos(self):
        '''
        Загружает список фотографий.
        @return: list
        '''
        photos = []
        resources = self._resource.get_resources('photos')
        for resource in resources:
            photo = Photo(resource)
            photos.append(photo)
        return photos
    
    def get_photos(self):
        '''
        Возвращает список фотографий.
        @return: list
        '''
        if self._photos is None:
            self._photos = self._get_photos()
        return self._photos


class Photo(object):
    '''
    Фотография.
    '''
    
    def __init__(self, resource):
        '''
        @param resource: Resource
        '''
        self._resource = resource
        
    def __str__(self):
        return '<Photo "%s">'%self.get_title().encode('utf8')
        
    def get_title(self):
        '''
        Возвращает название фотографии.
        @return: string
        '''
        return self._resource.get_property('title')
        
    def get_image(self):
        '''
        Возвращает тело фотографии.
        @return: string
        '''
        return self._resource.get_media()
