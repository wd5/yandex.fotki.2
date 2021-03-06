# encoding=utf8
'''
Обмен данными с сервером.
@author: Mic, 2012
'''

from datetime import datetime
from xml.etree.ElementTree import fromstring, tostring, Element, TreeBuilder, QName

from dm_yf.http import HttpRequest, HttpClient
from dm_yf.log import logger


# Пространства имен:
APP_NS = 'http://www.w3.org/2007/app'
ATOM_NS = 'http://www.w3.org/2005/Atom'
FOTKI_NS = 'yandex:fotki'

DOCUMENT_TYPE_ENTRY = 'entry'
DOCUMENT_TYPE_IMAGE = 'image'


def _get_document(url):
    '''
    Загружает документ по указанному адресу.
    @param url: string
    @return: string
    '''
    http_client = HttpClient()
    return http_client.request(url)


def _send_document(method, document_type, url, body):
    '''
    Отправляет документ на указанный адрес.
    Возвращает ответ сервера.
    @param method: string
    @param document_type: string
    @param url: string
    @param body: string
    @return: string
    '''
    if document_type == DOCUMENT_TYPE_ENTRY:
        content_type = 'application/atom+xml; charset=utf-8; type=entry'
    if document_type == DOCUMENT_TYPE_IMAGE:
        content_type = 'image/jpeg'
    http_client = HttpClient()
    return http_client.request(url, body, {'Content-Type': content_type}, method)


def _parse_resource_url(node, rel):
    '''
    Получает адрес ресурса.
    @param node: Element
    @param rel: string
    @return: string
    '''
    qname = str(QName(ATOM_NS, 'link'))
    child = node.find('%s[@rel="%s"]'%(qname, rel))
    if child is None:
        return None
    return child.attrib['href']


def _parse_resource(node):
    '''
    Создает объект ресурса в зависимости от его типа.
    @param node: Element
    @return: Resource
    '''
    qname = str(QName(ATOM_NS, 'id'))
    resource_id_node = node.find(qname)
    if resource_id_node is None:
        logger.error('resource id expected to be but not found')
        return None
    resource_id_parts = resource_id_node.text.split(':')
    resource_type = resource_id_parts[4]
    if resource_type == 'albums':
        return AlbumListResource(node)
    if resource_type == 'album':
        return AlbumResource(node)
    if resource_type == 'photo':
        return PhotoResource(node)
    logger.error('unknown resource type "%s"', resource_type)
    return None


def _parse_datetime(datetime_string):
    '''
    Разбирает дату и время из строки.
    @param datetime_string: string
    @return: datetime
    '''
    return datetime.strptime(datetime_string, '%Y-%m-%dT%H:%M:%SZ')


class Service(object):
    '''
    Сервис.
    '''

    # Список уже загруженных сервисов:
    _services = {}

    @classmethod
    def get(cls, url):
        '''
        Фабрика сервисов.
        @param url: string
        @return: Service
        '''
        if url not in cls._services:
            cls._services[url] = cls(url)
        return cls._services[url]

    def __init__(self, url):
        '''
        @param url: string
        '''
        self._url = url

    def _get_resource_url(self, resource_id):
        '''
        Возвращает адрес ресурса с указанным идентификатором.
        @param resource_id: string
        @return: string
        '''
        document = _get_document(self._url)
        root = fromstring(document)
        for node in root.findall('.//%s'%QName(APP_NS, 'collection')):
            if node.attrib['id'] == resource_id:
                return node.attrib['href']
        return None
    
    def _load_resource(self, url):
        '''
        Загружает ресур по указанному адресу.
        @param url: string
        @return: string
        '''
        document = _get_document(url)
        root = fromstring(document)
        return _parse_resource(root)
    
    def get_resource(self, resource_id):
        '''
        Возвращает ресурс с указанным идентификатором.
        @param resource_id: string
        @return: Resource
        '''
        logger.debug('loading resource %s for service %s', resource_id, self._url)
        url = self._get_resource_url(resource_id)
        return self._load_resource(url)


class Resource(object):
    '''
    Ресурс.
    '''
    
    def __init__(self, node):
        '''
        @param node: Element
        '''
        self._resources = None
        self._node = node
        
    def _get_node_by_name(self, name):
        '''
        Возвращает элемент по имени тега.
        @param name: string
        @return: string
        '''
        qname = str(QName(ATOM_NS, name))
        return self._node.find(qname)
        
    def _parse_resources(self, root):
        '''
        Разбирает список ресурсов.
        @param root: Element
        @return: list
        '''
        resources = []
        qname = str(QName(ATOM_NS, 'entry'))
        for node in root.findall(qname):
            resource = _parse_resource(node)
            resources.append(resource)
        return resources
    
    def _load_resources_page(self, url):
        '''
        Парсит одну страницу. Возвращает элементы страницы и ссылку на следующую страницу.
        @param url: string
        @return: list, string
        '''
        document = _get_document(url)
        root = fromstring(document)
        next_page_url = _parse_resource_url(root, 'next')
        return self._parse_resources(root), next_page_url
    
    def _load_resources(self, rel):
        '''
        Загружает список ресурсов.
        @param rel: string
        '''
        url = '%srpublished/'%_parse_resource_url(self._node, rel)
        all_resources, next_page_url = self._load_resources_page(url)
        while next_page_url is not None:
            resources, next_page_url = self._load_resources_page(next_page_url)
            all_resources.extend(resources)
        self._resources = all_resources

    def _get_resources(self, rel):
        '''
        Возвращает список ресурсов, содержащихся в данном.
        @param rel: string
        @return: list
        '''
        if self._resources is None:
            self._load_resources(rel)
        return self._resources
    
    def destroy(self):
        '''
        Уничтожает ресурс.
        '''
        # TODO: операция уничтожения должна производиться извне
        url = _parse_resource_url(self._node, 'self')
        _send_document(HttpRequest.METHOD_DELETE, DOCUMENT_TYPE_ENTRY, url, None)


class AlbumListResource(Resource):
    '''
    Ресурс списка альбомов.
    '''
    
    @property
    def albums(self):
        '''
        Возвращает список ресурсов альбомов.
        @return: list
        '''
        return self._get_resources('self')
    
    def _get_new_album_body(self, title):
        '''
        Формирует XML-элемент для нового альбома.
        @param title: string
        @return Element
        '''
        builder = TreeBuilder(Element)
        builder.start('entry', {'xmlns': ATOM_NS})
        builder.start('title', {})
        builder.data(title.decode('utf8'))
        builder.end('title')
        builder.end('entry')
        node = builder.close()
        return tostring(node)

    def add(self, title):
        '''
        Добавляет новый альбом и возвращает его ресурс.
        @param title: string
        @return: Resource
        '''
        url = _parse_resource_url(self._node, 'self')
        body = self._get_new_album_body(title)
        document = _send_document(HttpRequest.METHOD_POST, DOCUMENT_TYPE_ENTRY, url, body)
        resource = _parse_resource(fromstring(document))
        if self._resources is not None:
            self._resources.append(resource)
        return resource
    
    def _get_album_resource(self, title):
        '''
        Возвращает ресурс альбома по названию.
        @param title: string
        @return: AlbumResource
        '''
        for resource in self.albums:
            if resource.title == title:
                return resource
        return None
    
    def remove(self, title):
        '''
        Удаляет альбом.
        @param title: string
        '''
        resource = self._get_album_resource(title)
        if resource is None:
            return
        resource.destroy()
        self._resources.remove(resource)


class AlbumResource(Resource):
    '''
    Ресурс альбома.
    '''
    
    @property
    def title(self):
        '''
        Возвращает название альбома.
        @return: string
        '''
        title_node = self._get_node_by_name('title')
        if title_node is None:
            logger.error('album title not found')
            return None
        return title_node.text.encode('utf-8')
    
    @property
    def published(self):
        '''
        Возвращает дату публикации альбома.
        @return: datetime
        '''
        node = self._get_node_by_name('published')
        return _parse_datetime(node.text)
    
    @property
    def updated(self):
        '''
        Возвращает дату редактирования альбома.
        @return: datetime
        '''
        node = self._get_node_by_name('updated')
        return _parse_datetime(node.text)

    @property
    def photo_count(self):
        '''
        Возвращает количество фотографий в альбоме без их предварительной загрузки.
        @return: int
        '''
        qname = str(QName(FOTKI_NS, 'image-count'))
        image_count_node = self._node.find(qname)
        if image_count_node is None:
            logger.error('photo count not found')
            return None
        return int(image_count_node.attrib['value'])
    
    @property
    def photos(self):
        '''
        Возвращает список ресурсов фотографий.
        @return: list
        '''
        return self._get_resources('photos')

    def add(self, title, image_body):
        '''
        Добавляет фотографию в альбом и возвращает ее ресурс.
        @param title: string
        @param image_body: string
        @return: Resource
        '''
        url = _parse_resource_url(self._node, 'photos')
        document = _send_document(HttpRequest.METHOD_POST, DOCUMENT_TYPE_IMAGE, url, image_body)
        resource = _parse_resource(fromstring(document))
        if self._resources is not None:
            self._resources.append(resource)
        # TODO: грузить картинку и ставить заголовок в один запрос
        resource.title = title
        return resource
    
    def _get_photo_resource(self, title):
        '''
        Возвращает ресурс фотографии по названию.
        @param title: string
        @return: PhotoResource
        '''
        for resource in self.photos:
            if resource.title == title:
                return resource
        return None
    
    def remove(self, title):
        '''
        Удаляет фотографию.
        @param title: string
        '''
        resource = self._get_photo_resource(title)
        if resource is None:
            return
        resource.destroy()
        self._resources.remove(resource)


class PhotoResource(Resource):
    '''
    Ресурс фотографии.
    '''
    
    @property
    def remote_id(self):
        '''
        Возвращает идентификатор фотографии.
        @return: string
        '''
        id_node = self._get_node_by_name('id')
        if id_node is None:
            logger.error('photo id not found')
            return None
        return id_node.text
    
    @property
    def title(self):
        '''
        Возвращает название фотографии.
        @return: string
        '''
        title_node = self._get_node_by_name('title')
        if title_node is None:
            logger.error('photo title not found')
            return None
        return title_node.text.encode('utf-8')
    
    @title.setter
    def title(self, title):
        '''
        Задает название фотографии.
        @param title: string
        '''
        url = _parse_resource_url(self._node, 'edit')
        title_node = self._get_node_by_name('title')
        title_node.text = title
        _send_document(HttpRequest.METHOD_PUT, DOCUMENT_TYPE_ENTRY, url, tostring(self._node))
        
    @property
    def published(self):
        '''
        Возвращает дату публикации фотографии.
        @return: datetime
        '''
        node = self._get_node_by_name('published')
        return _parse_datetime(node.text)
    
    @property
    def updated(self):
        '''
        Возвращает дату редактирования фотографии.
        @return: datetime
        '''
        node = self._get_node_by_name('updated')
        return _parse_datetime(node.text)

    @property
    def size(self):
        '''
        Возвращает размер фотографии в байтах.
        @return: int
        '''
        qname = str(QName(FOTKI_NS, 'img'))
        img_node = self._node.find('%s[@size="orig"]'%qname)
        if img_node is None:
            logger.error('image size value not found')
            return None
        return int(img_node.attrib['bytesize'])

    @property
    def content(self):
        '''
        Возвращает прикрепленное медиа-содержимое.
        @return: string
        '''
        content_node = self._get_node_by_name('content')
        if content_node is None:
            logger.error('attached media not found')
            return None
        url = content_node.attrib['src']
        return _get_document(url)
