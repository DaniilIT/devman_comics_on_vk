from pathlib import Path
from random import randint
from sys import stderr

import requests
from dotenv import dotenv_values


XKCD_URL = 'https://xkcd.com'
API_VK_URL = 'https://api.vk.com'
API_VERSION = 5.124


def fetch_random_comic():
    """ Функция запрашивает у API xkcd случайное изображение с комиксом и сохраняет его.
    Возвращает название комикса и комментарий.
    """
    response = requests.get(f'{XKCD_URL}/info.0.json')
    response.raise_for_status()
    comic_last_number = int(response.json().get('num'))

    comic_number = randint(1, comic_last_number)

    response = requests.get(f'{XKCD_URL}/{comic_number}/info.0.json')
    response.raise_for_status()
    comic = response.json()
    image_url = comic.get('img')
    image_name = Path(image_url).name

    response = requests.get(image_url)
    response.raise_for_status()

    with open(image_name, 'wb') as f:
        f.write(response.content)

    return image_name, comic.get('alt')


def publish_comic_on_vk(implicit_flow_token, group_id, image_name, message):
    """ Функция публикует комикс в группе в vk
    """
    access_params = {
        'group_id': group_id,
        'access_token': implicit_flow_token,
        'v': API_VERSION,
    }
    response = requests.get(f'{API_VK_URL}/method/photos.getWallUploadServer', params=access_params)
    response.raise_for_status()
    upload_url = response.json().get('response').get('upload_url')

    with open(image_name, 'rb') as file:
        response = requests.post(upload_url, files={'photo': file})

    response.raise_for_status()
    params = access_params.copy()
    params.update(response.json())

    response = requests.post(f'{API_VK_URL}/method/photos.saveWallPhoto', params=params)
    response.raise_for_status()
    response = response.json().get('response')[0]
    media_id = response.get('id')
    owner_id = response.get('owner_id')

    params = access_params.copy()
    params.update({
        'owner_id': f'-{params["group_id"]}',
        'attachments': f'photo{owner_id}_{media_id}',
        'message': message,
        'from_group': 1,
    })
    response = requests.post(f'{API_VK_URL}/method/wall.post', params=params)
    response.raise_for_status()


def main():
    vk_implicit_flow_token = dotenv_values('.env')['VK_IMPLICIT_FLOW_TOKEN']
    vk_group_id = dotenv_values('.env')['VK_GROUP_ID']

    try:
        image_name, message = fetch_random_comic()
    except requests.exceptions.HTTPError:
        stderr.write(f'Не удалось сделать запрос к API xkcd.\n')
    else:
        try:
            publish_comic_on_vk(vk_implicit_flow_token, vk_group_id, image_name, message)
        except requests.exceptions.HTTPError:
            stderr.write(f'Не удалось сделать запрос к API VK.\n')
    finally:
        Path.unlink(image_name)


if __name__ == '__main__':
    main()
