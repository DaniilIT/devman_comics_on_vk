from pathlib import Path
from random import randint
from sys import stderr

import requests
from dotenv import dotenv_values


XKCD_URL = 'https://xkcd.com'
API_VK_URL = 'https://api.vk.com'
API_VERSION = 5.124


class VKError(Exception):
    pass


def check_response_vk(response):
    """ Функция проверяет ответ от API VK
    """
    is_error = response.get('error')
    if is_error:
        raise VKError(is_error['error_msg'])


def fetch_random_comic():
    """ Функция запрашивает у API xkcd случайное изображение с комиксом и сохраняет его.
    Возвращает название комикса и комментарий.
    """
    response = requests.get(f'{XKCD_URL}/info.0.json')
    response.raise_for_status()
    comic_last_number = int(response.json()['num'])

    comic_number = randint(1, comic_last_number)

    response = requests.get(f'{XKCD_URL}/{comic_number}/info.0.json')
    response.raise_for_status()
    comic = response.json()
    image_url = comic['img']
    image_name = Path(image_url).name

    response = requests.get(image_url)
    response.raise_for_status()

    with open(image_name, 'wb') as f:
        f.write(response.content)

    return image_name, comic['alt']


def upload_comic_on_server_vk(implicit_flow_token, group_id, image_name):
    """ Функция загружает изображение на сервер в vk.
    Возвращает информацию о загруженном файле.
    """
    params = {
        'group_id': group_id,
        'access_token': implicit_flow_token,
        'v': API_VERSION,
    }
    response = requests.get(f'{API_VK_URL}/method/photos.getWallUploadServer', params=params)
    response.raise_for_status()
    response = response.json()
    check_response_vk(response)
    upload_url = response['response']['upload_url']

    with open(image_name, 'rb') as file:
        response = requests.post(upload_url, files={'photo': file})

    response.raise_for_status()
    response = response.json()
    check_response_vk(response)
    return response['server'], response['photo'], response['hash']


def save_comic_in_group_album_vk(implicit_flow_token, group_id, uploaded_server, uploaded_photo, uploaded_hash):
    """ Функция сохраняет изображение в альбоме группы в vk.
    Возвращает идентификаторы сохраненного файла.
    """
    params = {
        'group_id': group_id,
        'access_token': implicit_flow_token,
        'v': API_VERSION,
        'server': uploaded_server,
        'photo': uploaded_photo,
        'hash': uploaded_hash,
    }

    response = requests.post(f'{API_VK_URL}/method/photos.saveWallPhoto', params=params)
    response.raise_for_status()
    response = response.json()
    check_response_vk(response)
    response = response['response'][0]
    media_id = response['id']
    owner_id = response['owner_id']
    return media_id, owner_id


def publish_comic_on_group_wall_vk(implicit_flow_token, group_id, media_id, owner_id, message):
    """ Функция публикует комикс на стене группы в vk
    """
    params = {
        'access_token': implicit_flow_token,
        'v': API_VERSION,
        'owner_id': f'-{group_id}',
        'attachments': f'photo{owner_id}_{media_id}',
        'message': message,
        'from_group': 1,
    }
    response = requests.post(f'{API_VK_URL}/method/wall.post', params=params)
    response.raise_for_status()
    response = response.json()
    check_response_vk(response)


def main():
    config = dotenv_values(".env")
    vk_implicit_flow_token = config['VK_IMPLICIT_FLOW_TOKEN']
    vk_group_id = config['VK_GROUP_ID']

    try:
        image_name, message = fetch_random_comic()
    except requests.exceptions.HTTPError:
        stderr.write(f'Не удалось сделать запрос к API xkcd.\n')
    else:
        try:
            uploaded_server, uploaded_photo, uploaded_hash = upload_comic_on_server_vk(vk_implicit_flow_token, vk_group_id, image_name)
            media_id, owner_id = save_comic_in_group_album_vk(vk_implicit_flow_token, vk_group_id, uploaded_server, uploaded_photo, uploaded_hash)
            publish_comic_on_group_wall_vk(vk_implicit_flow_token, vk_group_id, media_id, owner_id, message)
        except requests.exceptions.HTTPError:
            stderr.write(f'Не удалось сделать запрос к API VK.\n')
        except VKError as error:
            stderr.write(f'{error}\n')
    finally:
        Path.unlink(image_name)


if __name__ == '__main__':
    main()
