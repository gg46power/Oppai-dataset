"""Download Oppai-HQ dataset to current working directory."""

import os
import requests
import argparse
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, create_engine, DateTime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
import urllib
import cv2
import numpy as np

Base = declarative_base()


class OppaiDB(Base):
    __tablename__ = 'OppaiDB'
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_id = Column(String(256), default='')  # flickr image id
    url = Column(String(256), default='')
    filename = Column(String(256), default='')
    size = Column(Integer, default=0)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)

    # for bbox position top, left, width ,height
    t = Column(Integer, default=0)
    l = Column(Integer, default=0)
    w = Column(Integer, default=0)
    h = Column(Integer, default=0)

    def __str__(self):
        return "OppaiDB({}, {}, {}, {})".format(self.id, self.url)

    @staticmethod
    def get_all():
        sql = text('select * from OppaiDB')
        return OppaiDB.engine.execute(sql)

    @staticmethod
    def get_count():
        sql = text('select count(filename) from OppaiDB')
        sum_result = OppaiDB.engine.execute(sql)
        for r in sum_result:
            return r[0]

    @staticmethod
    def get_total_size():
        sql = text('select sum(size) from OppaiDB')
        sum_result = OppaiDB.engine.execute(sql)
        for r in sum_result:
            return r[0]

    @staticmethod
    def open_db(db_filename):
        engine: object = create_engine('sqlite:///' + db_filename)
        # print("Open oppai DB!, engine=", engine)
        DBsession = sessionmaker(bind=engine)
        OppaiDB.session = DBsession()
        OppaiDB.engine = engine

    @staticmethod
    def convertYolo(size, box):
        dw = 1. / (size[0])
        dh = 1. / (size[1])
        x = (box[0] + box[1]) / 2.0
        y = (box[2] + box[3]) / 2.0
        w = box[1] - box[0]
        h = box[3] - box[2]
        x = x * dw
        w = w * dw
        y = y * dh
        h = h * dh
        return (x, y, w, h)

    @staticmethod
    def get_voc_string(filename, orig_w, orig_h, l, t, w, h):
        voc_template = '''
<annotation>
    <folder>jpg</folder>
    <filename>%s</filename>
    <source>
        <database>The Oppai-HQ</database>
        <annotation>Oppai</annotation>
        <image>Flickr</image>
    </source>
    <owner>
        <flickrid>%s</flickrid>
        <name></name>
    </owner>
    <size>
        <width>%d</width>
        <height>%d</height>
        <depth>3</depth>
    </size>
    <segmented>0</segmented>
    <object>
        <name>Oppai</name>
        <bndbox>
            <xmin>%d</xmin>
            <ymin>%d</ymin>
            <xmax>%d</xmax>
            <ymax>%d</ymax>
        </bndbox>
    </object>
</annotation>'''
        flickr_id = os.path.basename(filename).replace("flickr_", "").replace(".jpg", "")
        output = str(voc_template) % (filename, flickr_id, orig_w, orig_h, l, t, l + w, t + h)
        return output


def choose_bytes_unit(num_bytes):
    b = int(np.rint(num_bytes))
    if b < (1024 * 1024):
        return 'KB', "%.2f" % round(num_bytes / 1024, 2)
    if b < (1024 * 1024 * 1024):
        return 'MB', "%.2f" % round(num_bytes / (1024 * 1024), 2)
    return 'GB', "%.2f" % round(num_bytes / (1024 * 1024 * 1024), 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download Oppai-HQ dataset to current working directory.')
    parser.add_argument('-c', '--crop', help='default=1, enable crop img to crop directory', type=int,
                        default=0, dest="crop")
    parser.add_argument('-x', '--xml', help='default=1, create xml file to xml directory', type=int,
                        default=1, dest="xml")
    parser.add_argument('-t', '--test', help='test script, Skip Image Download', type=int, default=0,
                        dest="test")
    parser.add_argument('-d', '--db', help='database path, default=oppai_lite.db', dest="db_filename",
                        default="oppai_lite.db")
    parser.add_argument('-i', '--info', help='get image information url', dest="info",
                        default=0)
    parser.add_argument('-y', '--yolo', help='output yolo format', dest="yolo",
                        default=1)


    args = parser.parse_args()

    IS_CROP = True if args.crop == 1 else False
    IS_XML = True if args.xml == 1 else False
    IS_TEST = False if args.test == 0 else True
    IS_INFO = False if args.info == 0 else True
    IS_YOLO = False if args.yolo == 0 else True

    # print("args=", IS_CROP, IS_XML, IS_TEST)

    OppaiDB.open_db(args.db_filename)
    print("Download Oppai-HQ Start ... using db:", args.db_filename)
    print()

    result = OppaiDB.get_all()
    total_size = OppaiDB.get_total_size()
    total_count = OppaiDB.get_count()

    size_unit, float_file_size = choose_bytes_unit(total_size)
    print("Total images count= ", total_count)
    print("Total size=", float_file_size, size_unit)
    print()

    # make download dirs:
    try:
        crop_path = os.path.join("download", "crop")
        xml_path = os.path.join("download", "xml")
        jpg_path = os.path.join("download", "jpg")
        os.makedirs("download", exist_ok=True)
        os.makedirs(crop_path, exist_ok=True)
        os.makedirs(xml_path, exist_ok=True)
        os.makedirs(jpg_path, exist_ok=True)
    except Exception as e:
        print("mkdir error:", e)

    index = 0

    # start
    for row in result:
        try:
            filename = row["filename"]
            index = index + 1

            prefix = "[%3d/%3d]" % (index, total_count)
            if os.path.exists(os.path.join(jpg_path, filename)):
                print(prefix, "[SKIP] file exist ", filename)
                continue

            choose_bytes_unit(total_size)
            size_unit, float_file_size = choose_bytes_unit(row["size"])
            print(prefix, "[Download]", row["url"], float_file_size, size_unit)

            if not IS_TEST:
                urllib.request.urlretrieve(row["url"], os.path.join(jpg_path, filename))

            if IS_YOLO:
                # call voc to xml for yolo
                yx, yy, yw, yh = OppaiDB.convertYolo([row["width"],row["height"]],
                      [row["l"],
                       row["l"] + row["w"],
                       row["t"],
                       row["t"] + row["h"]])
                yolo_txt = "0 " + str(yx) + " " + str(yy) + " " + str(yw) + " " + str(yh)
                yolo_open = open(os.path.join(jpg_path, filename.replace(".jpg", ".txt")), "w")
                yolo_open.write(yolo_txt)
                yolo_open.close()

            if IS_XML:
                full_voc_str = OppaiDB.get_voc_string(
                    os.path.join(jpg_path, filename),
                    row["width"],
                    row["height"],
                    row["l"],
                    row["t"],
                    row["w"],
                    row["h"],
                )
                xml_open = open(os.path.join(xml_path, filename.replace(".jpg", ".xml")), "w")
                xml_open.write(full_voc_str)
                xml_open.close()

            if IS_CROP:
                img = cv2.imread(os.path.join(jpg_path, filename))
                crop_img = img[row['l']:row['l'] + row["h"], row['t']:row['t'] + row["w"]]
                cv2.imwrite(os.path.join(crop_path, filename), crop_img)

            if IS_INFO:
                info_url = "https://www.flickr.com/photo.gne?id=" + row["image_id"]

                xml_open = open(os.path.join(xml_path, filename.replace(".jpg", "_info.txt")), "w")
                xml_open.write(info_url)
                xml_open.close()

        except Exception as e:
            print("something error, skip:", e)



