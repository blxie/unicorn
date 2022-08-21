#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Copyright (c) Megvii, Inc. and its affiliates.

import os
from loguru import logger

import cv2
import numpy as np
from pycocotools.coco import COCO

from ..dataloading import get_unicorn_datadir
from .datasets_wrapper import Dataset
"""2021.10.13 modified COCO dataset for SOT"""
"""22.01.15 COCO for MOTS Pretraining"""
import random

class COCOMOTSDataset(Dataset):
    """
    COCO MOTS dataset class.
    """

    def __init__(
        self,
        data_dir=None,
        json_file="instances_train2017.json",
        name="train2017",
        img_size=(416, 416),
        preproc=None,
        cache=False,
        min_sz=0,
        cat_names_in_coco=None,
        cat_names_full=None,
        max_inst=100
    ):
        """
        COCO dataset initialization. Annotation data are read into memory by COCO API.
        Args:
            data_dir (str): dataset root directory
            json_file (str): COCO json file name
            name (str): COCO data name (e.g. 'train2017' or 'val2017')
            img_size (int): target image size after pre-processing
            preproc: data augmentation strategy
        """
        super().__init__(img_size)
        if data_dir is None:
            data_dir = os.path.join(get_unicorn_datadir(), "COCO")
        self.data_dir = data_dir
        self.json_file = json_file
        self.min_sz = min_sz
        self.max_inst = max_inst
        self.coco = COCO(os.path.join(self.data_dir, "annotations", self.json_file))
        if cat_names_in_coco is None:
            self.ids = self.coco.getImgIds() # all images ids
        else:
            # obtain images ids containing given classes
            cat_ids = self.coco.getCatIds(catNms=cat_names_in_coco)
            self.ids = []
            for c in cat_ids:
                self.ids += self.coco.getImgIds(catIds=[c]) # all images ids
            self.ids = list(set(self.ids))
        self.class_ids = sorted(self.coco.getCatIds()) # 1~90
        # print("self.class_ids: ", self.class_ids)
        cats = self.coco.loadCats(self.coco.getCatIds())
        self._classes = tuple([c["name"] for c in cats]) # ("person", "bicycle", ...)
        # print("self._classes: ", self._classes)
        self.cat_names_in_coco = cat_names_in_coco
        self.cat_names_full = cat_names_full
        self.imgs = None
        self.name = name
        self.img_size = img_size
        self.preproc = preproc
        self.annotations = self._load_coco_annotations()
        if cache:
            self._cache_images()

    def __len__(self):
        return len(self.ids)

    def __del__(self):
        del self.imgs

    def _load_coco_annotations(self):
        return [self.load_anno_from_ids(_ids) for _ids in self.ids]

    def _cache_images(self):
        logger.warning(
            "\n********************************************************************************\n"
            "You are using cached images in RAM to accelerate training.\n"
            "This requires large system RAM.\n"
            "Make sure you have 200G+ RAM and 136G available disk space for training COCO.\n"
            "********************************************************************************\n"
        )
        max_h = self.img_size[0]
        max_w = self.img_size[1]
        cache_file = self.data_dir + "/img_resized_cache_" + self.name + ".array"
        if not os.path.exists(cache_file):
            logger.info(
                "Caching images for the first time. This might take about 20 minutes for COCO"
            )
            self.imgs = np.memmap(
                cache_file,
                shape=(len(self.ids), max_h, max_w, 3),
                dtype=np.uint8,
                mode="w+",
            )
            from tqdm import tqdm
            from multiprocessing.pool import ThreadPool

            NUM_THREADs = min(8, os.cpu_count())
            loaded_images = ThreadPool(NUM_THREADs).imap(
                lambda x: self.load_resized_img(x),
                range(len(self.annotations)),
            )
            pbar = tqdm(enumerate(loaded_images), total=len(self.annotations))
            for k, out in pbar:
                self.imgs[k][: out.shape[0], : out.shape[1], :] = out.copy()
            self.imgs.flush() # write to disk
            pbar.close()
        else:
            logger.warning(
                "You are using cached imgs! Make sure your dataset is not changed!!\n"
                "Everytime the self.input_size is changed in your exp file, you need to delete\n"
                "the cached data and re-generate them.\n"
            )

        logger.info("Loading cached imgs...")
        self.imgs = np.memmap(
            cache_file,
            shape=(len(self.ids), max_h, max_w, 3),
            dtype=np.uint8,
            mode="r+",
        )

    def load_anno_from_ids(self, id_):
        im_ann = self.coco.loadImgs(id_)[0]
        width = im_ann["width"]
        height = im_ann["height"]
        anno_ids = self.coco.getAnnIds(imgIds=[int(id_)], iscrowd=False)
        annotations = self.coco.loadAnns(anno_ids)
        objs = []
        cls_list = []
        for obj in annotations:
            if obj["category_id"] > 80:
                continue
            x1 = np.max((0, obj["bbox"][0]))
            y1 = np.max((0, obj["bbox"][1]))
            x2 = np.min((width, x1 + np.max((0, obj["bbox"][2]))))
            y2 = np.min((height, y1 + np.max((0, obj["bbox"][3]))))
            cat_name = self._classes[(obj["category_id"] - 1)] # category name
            if self.cat_names_in_coco is not None:
                if cat_name in self.cat_names_in_coco:
                    cls_list.append(self.cat_names_full.index(cat_name))
                    if obj["area"] > 0 and (x2-x1)>self.min_sz and (y2-y1)>self.min_sz:
                        obj["clean_bbox"] = [x1, y1, x2, y2]
                        objs.append(obj)
            else:
                if obj["area"] > 0 and (x2-x1)>self.min_sz and (y2-y1)>self.min_sz:
                    obj["clean_bbox"] = [x1, y1, x2, y2]
                    objs.append(obj)

        num_objs = min(self.max_inst, len(objs))

        res = np.zeros((num_objs, 6))

        for ix, obj in enumerate(objs):
            if ix == num_objs:
                break
            # if obj["category_id"] == 90:
            #     print("category_id 90")
            if self.cat_names_in_coco is not None:
                cls = cls_list[ix]
            else:
                cls = self.class_ids.index(obj["category_id"]) # 0~89
            res[ix, 0:4] = obj["clean_bbox"]
            res[ix, 4] = cls
            res[ix, 5] = ix + 1

        r = min(self.img_size[0] / height, self.img_size[1] / width)
        res[:, :4] *= r # coordinates on the resized image

        img_info = (height, width) # original size
        resized_info = (int(height * r), int(width * r)) # size after resizing

        file_name = (
            im_ann["file_name"]
            if "file_name" in im_ann
            else "{:012}".format(id_) + ".jpg"
        )

        return (res, img_info, resized_info, file_name)

    def load_anno(self, index):
        return self.annotations[index][0]

    def load_resized_img(self, index):
        img = self.load_image(index) # BGR Image
        r = min(self.img_size[0] / img.shape[0], self.img_size[1] / img.shape[1])
        resized_img = cv2.resize(
            img,
            (int(img.shape[1] * r), int(img.shape[0] * r)),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.uint8)
        return resized_img

    def load_image(self, index):
        file_name = self.annotations[index][3]

        img_file = os.path.join(self.data_dir, self.name, file_name)

        img = cv2.imread(img_file)
        assert img is not None

        return img

    def load_resized_mask(self, index):
        mask = self.load_mask(index)
        if mask is not None:
            r = min(self.img_size[0] / mask.shape[0], self.img_size[1] / mask.shape[1])
            resized_mask = cv2.resize(
                mask,
                (int(mask.shape[1] * r), int(mask.shape[0] * r)),
                interpolation=cv2.INTER_LINEAR,
            ).astype(np.float32)
            # resize would transform (H, W, 1) to (H, W). So we need to manually add an axis
            if len(resized_mask.shape) == 2:
                resized_mask = resized_mask[:, :, None] # to (H, W, 1)
            return resized_mask
        else:
            return np.zeros((self.img_size[0], self.img_size[1], 0))

    def load_mask(self, index):
        id_ = self.ids[index]
        im_ann = self.coco.loadImgs(id_)[0]
        width = im_ann["width"]
        height = im_ann["height"]
        anno_ids = self.coco.getAnnIds(imgIds=[int(id_)], iscrowd=False)
        annotations = self.coco.loadAnns(anno_ids)
        masks = []
        for obj in annotations:
            # assert(type(obj['segmentation']) == list)
            if obj["category_id"] > 80:
                continue
            x1 = np.max((0, obj["bbox"][0]))
            y1 = np.max((0, obj["bbox"][1]))
            x2 = np.min((width, x1 + np.max((0, obj["bbox"][2]))))
            y2 = np.min((height, y1 + np.max((0, obj["bbox"][3]))))
            cat_name = self._classes[(obj["category_id"] - 1)] # category name
            if self.cat_names_in_coco is not None:
                if cat_name in self.cat_names_in_coco:
                    # cls_list.append(self.cat_names_full.index(cat_name))
                    if obj["area"] > 0 and (x2-x1)>=self.min_sz and (y2-y1)>=self.min_sz:
                        masks.append(self.coco.annToMask(obj))
            else:
                if obj["area"] > 0 and (x2-x1)>=self.min_sz and (y2-y1)>=self.min_sz:
                    masks.append(self.coco.annToMask(obj))
            if len(masks) == self.max_inst:
                break
        if len(masks) > 0:
            mask_arr = np.stack(masks, axis=-1).astype(np.float32) # (H, W, N)
        else:
            # mask_arr = None
            mask_arr = np.zeros((self.img_size[0], self.img_size[1], 0))
        return mask_arr

    def pull_item(self, idx, num_frames=2):
        """idx is invalid"""
        valid = False
        while not valid:
            index = random.randint(0, self.__len__() - 1)
            res, img_info, resized_info, _ = self.annotations[index]
            num_objs = res.shape[0]
            valid = num_objs > 0
            if valid:
                if self.imgs is not None:
                    pad_img = self.imgs[index]
                    img = pad_img[: resized_info[0], : resized_info[1], :].copy()
                    raise ValueError("Instance Segmentation doesn't support cache for now")
                else:
                    img = self.load_resized_img(index) # resized image (without padding)
                    # mask_rsz = self.load_resized_mask(index) # resized mask (without padding) (H, W, N), N is the number of instances
                    mask_rsz = self.load_mask(index) # resized mask (without padding) (H, W, N), N is the number of instances
        assert res.shape[0] == mask_rsz.shape[-1]
        return [(img, res, mask_rsz)] * 2, None, None
    
    def pull_item_id(self, seq_id, obj_id, num_frames):
        res, _, resized_info, _ = self.annotations[seq_id]
        if self.imgs is not None:
            pad_img = self.imgs[seq_id]
            img = pad_img[: resized_info[0], : resized_info[1], :].copy()
        else:
            img = self.load_resized_img(seq_id) # resized image (without padding)
        # img: resized image, res: coordinates and class id on the resized image
        target = res[obj_id: obj_id+1]
        target[0, -1] = 0 # for SOT, all instances share class id 0
        result = (img, target.copy())
        # for static image dataset, we duplicate the result
        return [result] * num_frames

    @Dataset.mosaic_getitem
    def __getitem__(self, index):
        """
        One image / label pair for the given index is picked up and pre-processed.

        Args:
            index (int): data index

        Returns:
            img (numpy.ndarray): pre-processed image
            padded_labels (torch.Tensor): pre-processed label data.
                The shape is :math:`[max_labels, 5]`.
                each label consists of [class, xc, yc, w, h]:
                    class (float): class index.
                    xc, yc (float) : center of bbox whose values range from 0 to 1.
                    w, h (float) : size of bbox whose values range from 0 to 1.
            info_img : tuple of h, w.
                h, w (int): original shape of the image
            img_id (int): same as the input index. Used for evaluation.
        """
        img, target, img_info, img_id = self.pull_item(index)

        if self.preproc is not None:
            img, target = self.preproc(img, target, self.input_dim)
        return img, target, img_info, img_id
