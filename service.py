import argparse
import logging
import logging.handlers
import os
import sys

from rapidhost import RapidhostAPI

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument("-u", "--username", required=True, help="Username")
    ap.add_argument("-p", "--password", required=True, help="Password")
    ap.add_argument("-r", "--root", help="Root path for downloaded files", default='.')
    args = vars(ap.parse_args())

    PATH, _ = os.path.split(sys.argv[0])

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("").setLevel(logging.DEBUG)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fh = logging.handlers.RotatingFileHandler(os.path.join(PATH, 'rapidhost.log'), maxBytes=1024 ** 2, backupCount=10)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s [%(levelname)s] %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    r = RapidhostAPI(args['username'], args['password'], args['root'])
    r.set_filter('rpi')
    r.run_service(repeat_time=10)
