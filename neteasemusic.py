from bs4 import BeautifulSoup
import requests
import json
from tqdm import tqdm
import sqlite3
import os
from datetime import datetime
import matplotlib. dates as mdates
import matplotlib. pyplot as plt
from matplotlib.pyplot import figure
import matplotlib.ticker as ticker
import re


headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'zh-CN,zh;q=0.8,en;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Cookie': '',
        'DNT': '1',
        'Host': 'music.163.com',
        'Pragma': 'no-cache',
        'Referer': 'http://music.163.com/',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
    }

session = requests.session()
session.headers.update(headers)

'''
解析网易云音乐windows版的数据库
'''
try:
    con = sqlite3.connect('%s/Netease/CloudMusic/Library/webdb.dat' % os.environ['localappdata'])
    cur = con.cursor()

    # 获取用户id
    userid_list = cur.execute('''SELECT pids, uid FROM web_user_playlist''').fetchall()
    cnt = 1
    print("id, name")
    for data in userid_list:
        addr = 'https://music.163.com/user/home?id=%s' % data[1]
        response = requests.get(addr, headers=headers)
        soup = BeautifulSoup(response.content.decode(), 'html.parser')
        print("%d, %s" % (cnt, json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['title']))
        cnt += 1
    print('------------select your id------------')
    sel = int(input())
    playlist_list = [item for item in userid_list[sel-1][0].strip().split(',') if item != '']

    # 获取歌单id
    cnt = 1
    print("id, name")
    for data in playlist_list:
        try:
            addr = 'https://music.163.com/playlist?id=%s' % data
            response = requests.get(addr, headers=headers)
            soup = BeautifulSoup(response.content.decode(), 'html.parser')
            print("%d, %s" % (cnt, json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['title']))
            cnt += 1
        except:
            print("%d, %s" % (cnt, "PRIVATE LIST"))
            cnt += 1
    print('------------select your id------------')
    sel = int(input())
    playlistid = playlist_list[sel-1]

    # 获取歌单歌曲
    album_list = cur.execute('''SELECT a.tid, b.track FROM web_playlist_track a
    LEFT JOIN web_track b
    ON a.tid = b.tid
    WHERE a.pid = '%s' ''' % (playlistid)).fetchall()

    print("playlist %s" % playlist_list[sel-1][0])
    print("total %d songs" % len(album_list))
    failed_list = []

    # 生成歌曲所属专辑时间的文件
    # 根据专辑id请求网页，获得专辑时间
    with open('result.txt', 'w', encoding='utf-8') as target:
        for _, data in tqdm(album_list):
            albuminfo = json.loads(data)
            try:
                addr = 'https://music.163.com/album?id=' + str(albuminfo['album']['id'])
                song = albuminfo['name']
                response = requests.get(addr, headers=headers)
                if response.status_code != 200:
                    failed_list.append((albuminfo, "request failed"))
                else:
                    soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'html.parser')
                    try:
                        date = json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['pubDate']
                        target.writelines(song + ',' + date + '\n')
                    except Exception as e:
                        failed_list.append((albuminfo, "content error"))
            except TypeError:
                failed_list.append((albuminfo, "type error"))

    print('%d songs failed' % len(failed_list))
    for item in failed_list:
        print(item)

    # 绘制散点图
    dates = []
    with open('result.txt', 'r', encoding='utf-8') as f:
        for line in f:
            dates.append(re.search('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', line).group())

    ys = [datetime.strptime(m,'%Y-%m-%dT%H:%M:%S' ).date() for m in dates]
    ys.reverse()
    xs = list(range(len(ys)))
    # setting
    width = 8
    height = 6
    figure(figsize=(width, height), dpi=100)
    plt.gca().yaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gca().yaxis.set_major_locator(mdates.DayLocator())
    # plot
    plt.scatter(xs, ys, s=4)
    plt.xticks([])
    plt.yticks([])
    plt.gca().yaxis.set_major_locator(ticker.MultipleLocator(((max(ys)-min(ys))/height/2).days))
    plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(len(xs)/width/2))
    plt.savefig('result.png', bbox_inches='tight')
    plt.show()

except Exception as e:
    print(e)
    os._exit(-1)

finally:
    con.close()