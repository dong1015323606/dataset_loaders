import numpy as np
import os
import time

import dataset_loaders
from dataset_loaders.parallel_loader import ThreadedDataset


floatX = 'float32'


class CamvidDataset(ThreadedDataset):
    name = 'camvid'
    nclasses = 11
    debug_shape = (360, 480, 3)

    # optional arguments
    data_shape = (360, 480, 3)

    _void_labels = [11]
    _cmap = {
        0: (128, 128, 128),    # sky
        1: (128, 0, 0),        # building
        2: (192, 192, 128),    # column_pole
        3: (128, 64, 128),     # road
        4: (0, 0, 192),        # sidewalk
        5: (128, 128, 0),      # Tree
        6: (192, 128, 128),    # SignSymbol
        7: (64, 64, 128),      # Fence
        8: (64, 0, 128),       # Car
        9: (64, 64, 0),        # Pedestrian
        10: (0, 128, 192),     # Bicyclist
        11: (0, 0, 0)}         # Void
    _mask_labels = {0: 'sky', 1: 'building', 2: 'column_pole', 3: 'road',
                    4: 'sidewalk', 5: 'tree', 6: 'sign', 7: 'fence', 8: 'car',
                    9: 'pedestrian', 10: 'byciclist', 11: 'void'}

    _filenames = None

    @property
    def filenames(self):
        if self._filenames is None:
            # Get file names for this set and year
            filenames = []
            with open(os.path.join(self.path, self.which_set + '.txt')) as f:
                for fi in f.readlines():
                    raw_name = fi.strip()
                    raw_name = raw_name.split("/")[4]
                    raw_name = raw_name.strip()
                    filenames.append(raw_name)
            self._filenames = filenames
        return self._filenames

    def __init__(self, which_set='train', with_filenames=False, *args,
                 **kwargs):

        self.which_set = "val" if which_set == "valid" else which_set
        self.with_filenames = with_filenames
        self.path = os.path.join(
            dataset_loaders.__path__[0], 'datasets', 'camvid', 'segnet')
        self.sharedpath = '/data/lisa/exp/visin/_datasets/camvid/segnet'

        if self.which_set == "train":
            self.image_path = os.path.join(self.path, "train")
            self.mask_path = os.path.join(self.path, "trainannot")
        elif self.which_set == "val":
            self.image_path = os.path.join(self.path, "val")
            self.mask_path = os.path.join(self.path, "valannot")
        elif self.which_set == "test":
            self.image_path = os.path.join(self.path, "test")
            self.mask_path = os.path.join(self.path, "testannot")

        # constructing the ThreadedDataset
        # it also creates/copies the dataset in self.path if not already there
        super(CamvidDataset, self).__init__(*args, **kwargs)

    def get_names(self):
        sequences = []
        seq_length = self.seq_length

        prefix_list = np.unique(np.array([el[:6] for el in self.filenames]))

        self.video_length = {}
        # cycle through the different videos
        for prefix in prefix_list:
            seq_per_video = self.seq_per_video
            frames = [el for el in self.filenames if prefix in el]
            video_length = len(frames)
            self.video_length[prefix] = video_length

            # Fill sequences with (prefix, frame_idx)
            max_num_sequences = video_length - seq_length + 1
            if (not self.seq_length or not self.seq_per_video or
                    self.seq_length >= video_length):
                # Use all possible frames
                for el in [(prefix, f) for f in frames[
                        :max_num_sequences:self.seq_length - self.overlap]]:
                    sequences.append(el)
            else:
                if max_num_sequences < seq_per_video:
                    # If there are not enough frames, cap seq_per_video to
                    # the number of available frames
                    print("/!\ Warning : you asked {} sequences of {} "
                          "frames each but video {} only has {} "
                          "frames".format(seq_per_video, seq_length,
                                          prefix, video_length))
                    seq_per_video = max_num_sequences

                if self.overlap != self.seq_length - 1:
                    raise('Overlap other than seq_length - 1 is not '
                          'implemented')

                # pick `seq_per_video` random indexes between 0 and
                # (video length - sequence length)
                first_frame_indexes = self.rng.permutation(range(
                    max_num_sequences))[0:seq_per_video]

                for i in first_frame_indexes:
                    sequences.append((prefix, frames[i]))

        return np.array(sequences)

    def load_sequence(self, first_frame):
        """
        Load ONE clip/sequence

        Auxiliary function which loads a sequence of frames with
        the corresponding ground truth and potentially filenames.
        Returns images in [0, 1]
        """
        from skimage import io
        X = []
        Y = []
        F = []

        prefix, first_frame_name = first_frame

        if (self.seq_length is None or
                self.seq_length > self.video_length[prefix]):
            seq_length = self.video_length[prefix]
        else:
            seq_length = self.seq_length

        start_idx = self.filenames.index(first_frame_name)
        for frame in self.filenames[start_idx:start_idx + seq_length]:
            img = io.imread(os.path.join(self.image_path, frame))
            mask = io.imread(os.path.join(self.mask_path, frame))

            img = img.astype(floatX) / 255.
            mask = mask.astype('int32')

            X.append(img)
            Y.append(mask)
            F.append(frame)

        X = np.array(X)
        Y = np.array(Y)
        F = np.array(F)

        if self.with_filenames:
            return X, Y, F
        else:
            return X, Y


def test3():
    trainiter = CamvidDataset(
        which_set='train',
        batch_size=5,
        seq_per_video=0,
        seq_length=0,
        crop_size=(224, 224),
        split=.75,
        get_one_hot=True,
        get_01c=True,
        use_threads=True,
        nthreads=5)

    train_nsamples = trainiter.nsamples
    nclasses = trainiter.get_n_classes()
    nbatches = trainiter.get_n_batches()
    train_batch_size = trainiter.get_batch_size()
    print("Train %d" % (train_nsamples))

    start = time.time()
    max_epochs = 5

    for epoch in range(max_epochs):
        for mb in range(nbatches):
            train_group = trainiter.next()

            # train_group checks
            assert train_group[0].ndim == 4
            assert train_group[0].shape[0] <= train_batch_size
            assert train_group[0].shape[1] == 224
            assert train_group[0].shape[2] == 224
            assert train_group[0].shape[3] == 3
            assert train_group[0].min() >= 0
            assert train_group[0].max() <= 1
            assert train_group[1].ndim == 3
            assert train_group[1].shape[0] <= train_batch_size
            assert train_group[1].shape[1] == 224
            assert train_group[1].shape[2] == 224
            assert train_group[1].shape[3] == nclasses

            # time.sleep approximates running some model
            time.sleep(0.1)
            stop = time.time()
            tot = stop - start
            print("Threaded time: %s" % (tot))
            print("Minibatch %s" % str(mb))
        print('ended epoch --> should reset!')
        time.sleep(2)


def test1():
    d = CamvidDataset(
        which_set='train',
        batch_size=5,
        seq_per_video=4,
        seq_length=0,
        crop_size=(224, 224))
    start = time.time()
    n_minibatches_to_run = 1000
    itr = 1
    while True:
        image_group = d.next()
        if image_group is None:
            raise NotImplementedError()
        # time.sleep approximates running some model
        time.sleep(1)
        stop = time.time()
        tot = stop - start
        print("Minibatch %s" % str(itr))
        print("Time ratio (s per minibatch): %s" % (tot / float(itr)))
        print("Tot time: %s" % (tot))
        itr += 1
        # test
        if itr >= n_minibatches_to_run:
            break


def test2():
    d = CamvidDataset(
        which_set='train',
        with_filenames=True,
        batch_size=5,
        seq_per_video=0,
        seq_length=10,
        overlap=10,
        get_one_hot=True,
        crop_size=(224, 224))
    for i, _ in enumerate(range(d.epoch_length)):
        image_group = d.next()
        if image_group is None:
            raise NotImplementedError()
        sh = image_group[0].shape
        print(image_group[2])
        if sh[1] != 2:
            raise RuntimeError()


if __name__ == '__main__':
    test2()
