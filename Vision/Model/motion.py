import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import os
import cv2
import csv
from itertools import combinations
import collections
import random

class Motion(object):
    width = 48
    height = 48
    motions_ = ["b", "bw", "t", "p", "cc", "cf", "r", "w", "n"]
    motions =  ["batting", "batting_waiting", "throwing", "pitching", "catch_catcher", "catch_field", "run", "walking", "nope"]
    rgb = 3

    def conv2d(self, input, name, filter_size, output_channel, strides=[1, 1, 1, 1]):
        input_channel = input.shape[3]
        with tf.variable_scope(name):
            W = tf.get_variable(name=name+"_W",
                                shape=[filter_size, filter_size, input_channel, output_channel],
                                initializer=tf.contrib.layers.xavier_initializer(uniform=False))
            b = tf.get_variable(name=name+"_b",
                                shape=[output_channel],
                                initializer=tf.contrib.layers.xavier_initializer(uniform=False))
            c = tf.nn.conv2d(input=input,
                             filter=W,
                             strides=strides,
                             padding="SAME")
            c = tf.nn.bias_add(c, b)
            c = tf.nn.leaky_relu(c)
            return c

    def deconv2d(self, input, name, filter_size, output_channel, strides=[1, 1]):
        with tf.variable_scope(name):
            out = tf.layers.conv2d_transpose(inputs=input,
                                       filters=output_channel,
                                       kernel_size=[filter_size, filter_size],
                                       strides=strides,
                                       padding="SAME",
                                       kernel_initializer=tf.contrib.layers.xavier_initializer(uniform=False),
                                       bias_initializer=tf.contrib.layers.xavier_initializer(uniform=False),
                                       activation=tf.nn.leaky_relu)
        return out

    def maxpool(self, input, name, filter_size, strides=[1, 2, 2, 1]):
        with tf.variable_scope(name):
            out = tf.nn.max_pool(value=input,
                                 ksize=[1, filter_size, filter_size, 1],
                                 strides=strides,
                                 padding="SAME")
        return out

    def upsample(self, input, name, times):
        with tf.variable_scope(name):
            out = tf.image.resize_bilinear(images=input,
                                           size=[int(input.shape[1] * times), int(input.shape[2] * times)])
        return out

    def fc(self, input, name, output_channel):
        input_channel = input.shape[1]
        with tf.variable_scope(name):
            W = tf.get_variable(name=name+"_W",
                                shape=[input_channel, output_channel],
                                initializer=tf.contrib.layers.xavier_initializer(uniform=False))
            b = tf.get_variable(name=name+"_b",
                                shape=[output_channel],
                                initializer=tf.contrib.layers.xavier_initializer(uniform=False))
            out = tf.nn.leaky_relu(tf.add(tf.matmul(input, W), b))
        return out

class CAE(Motion):
    def __init__(self):
        self.image = tf.placeholder(tf.float32, [None, self.height, self.width, self.rgb])
        self.keep_prob = tf.placeholder(tf.float32)

        with tf.variable_scope("CAE"):
            out = self.conv2d(self.image, name="conv_1", filter_size=3, output_channel=16)
            out = self.maxpool(out, name="pool_1", filter_size=2)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.conv2d(out, name="conv_2", filter_size=3, output_channel=32)
            out = self.conv2d(out, name="conv_3", filter_size=3, output_channel=32)
            out = self.maxpool(out, name="pool_2", filter_size=2)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.conv2d(out, name="conv_4", filter_size=3, output_channel=64)
            out = self.conv2d(out, name="conv_5", filter_size=3, output_channel=64)
            out = self.maxpool(out, name="pool_3", filter_size=2)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = tf.reshape(out, shape=[-1, 6 * 6 * 64])
            out = self.fc(out, name="fc_1", output_channel=6 * 6 * 32)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.fc(out, name="fc_2", output_channel=6 * 6 * 16)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.fc(out, name="fc_3", output_channel=64)

            out = self.fc(out, name="fc_4", output_channel=6 * 6 * 16)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.fc(out, name="fc_5", output_channel=6 * 6 * 32)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = self.fc(out, name="fc_6", output_channel=6 * 6 * 64)
            out = tf.nn.dropout(out, keep_prob=self.keep_prob)

            out = tf.reshape(out, shape=[-1, 6, 6, 64])

            out = self.deconv2d(out, name="dconv_1", filter_size=3, output_channel=64)
            out = self.deconv2d(out, name="dconv_2", filter_size=3, output_channel=32)
            out = self.upsample(out, name="ups_1", times=2)

            out = self.deconv2d(out, name="dconv_3", filter_size=3, output_channel=32)
            out = self.deconv2d(out, name="dconv_4", filter_size=3, output_channel=16)
            out = self.upsample(out, name="ups_2", times=2)

            out = self.deconv2d(out, name="dconv_5", filter_size=3, output_channel=3)
            out = self.upsample(out, name="ups_2", times=2)

            out = tf.reshape(out, shape=[-1, 48 * 48 * 3])
            out = self.fc(out, name="fc_7", output_channel=48 * 48 * 3)

        self.output = tf.reshape(out, shape=[-1, 48, 48, 3])

    def test(self):
        sess = tf.Session()
        all_vars = tf.global_variables()
        cae = [k for k in all_vars if k.name.startswith("CAE")]
        saver = tf.train.Saver(cae)
        saver.restore(sess, './CAE/CAE.ckpt')

        for i in range(0, 10):
            f = random.randint(0, 10000)
            f = str(f)+".jpg"
            x = cv2.resize(cv2.imread("D:\\work\\kbo\\_data\\_motion\\"+f), (self.width, self.height))
            x = np.array([x])

            o = sess.run(self.output, feed_dict={self.image: x, self.keep_prob: 1})
            o = np.resize(o, [self.width, self.height, 3])

            cv2.imwrite(f, o)

class Motion_Model(Motion):
    def __init__(self, sess):
        self.sess = sess
        self.length = 10
        self.num_hidden = 64

        self.image = tf.placeholder(tf.float32, [None, self.length, self.height, self.width, self.rgb])
        self.Y = tf.placeholder(tf.float32, [None, len(self.motions)])
        self.L = tf.placeholder(tf.int32, [None])
        self.keep_prob = tf.placeholder(tf.float32)

        with tf.variable_scope("CAE", reuse=tf.AUTO_REUSE):
            for i in range(self.length):
                input = self.image[:, i, :, :, :]
                out = self.conv2d(input, name="conv_1", filter_size=3, output_channel=16)
                out = self.maxpool(out, name="pool_1", filter_size=2)
                out = tf.nn.dropout(out, keep_prob=self.keep_prob)

                out = self.conv2d(out, name="conv_2", filter_size=3, output_channel=32)
                out = self.conv2d(out, name="conv_3", filter_size=3, output_channel=32)
                out = self.maxpool(out, name="pool_2", filter_size=2)
                out = tf.nn.dropout(out, keep_prob=self.keep_prob)

                out = self.conv2d(out, name="conv_4", filter_size=3, output_channel=64)
                out = self.conv2d(out, name="conv_5", filter_size=3, output_channel=64)
                out = self.maxpool(out, name="pool_3", filter_size=2)
                out = tf.nn.dropout(out, keep_prob=self.keep_prob)

                out = tf.reshape(out, shape=[-1, 6 * 6 * 64])
                out = self.fc(out, name="fc_1", output_channel=6 * 6 * 32)
                out = tf.nn.dropout(out, keep_prob=self.keep_prob)

                out = self.fc(out, name="fc_2", output_channel=6 * 6 * 16)
                out = tf.nn.dropout(out, keep_prob=self.keep_prob)

                out = self.fc(out, name="fc_3", output_channel=64)
                out = tf.reshape(out, shape=[-1, 1, 64])

                if (i == 0):
                    features = out
                else:
                    features = tf.concat([features, out], 1)

        with tf.variable_scope("cls"):
            lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(self.num_hidden)
            lstm_cell = tf.nn.rnn_cell.DropoutWrapper(lstm_cell, output_keep_prob=self.keep_prob)
            all_outputs, states = tf.nn.dynamic_rnn(cell=lstm_cell, inputs=features, sequence_length=self.L, dtype=tf.float32)
            outputs = self.last_relevant(all_outputs, self.L)

            W = tf.Variable(tf.random_normal([self.num_hidden, len(self.motions)]))
            b = tf.Variable(tf.random_normal([len(self.motions)]))

        self.model = tf.matmul(outputs, W) + b
        self.output = tf.nn.softmax(self.model)

        all_vars = tf.global_variables()
        cls = [k for k in all_vars if k.name.startswith("CAE") or k.name.startswith("cls")]
        saver = tf.train.Saver(cls)
        saver.restore(self.sess, './_model/motion/CLS/cls.ckpt')

    def last_relevant(self, seq, length):
        batch_size = tf.shape(seq)[0]
        max_length = int(seq.get_shape()[1])
        input_size = int(seq.get_shape()[2])
        index = tf.range(0, batch_size) * max_length + (length - 1)
        flat = tf.reshape(seq, [-1, input_size])
        return tf.gather(flat, index)

    def predict(self, person_seq):
        person_seq = person_seq[-self.length:]

        dataset = [cv2.resize(d, (self.width, self.height)) for d in person_seq]
        leng = len(dataset)

        pad = np.zeros((self.width, self.height, self.rgb))
        if (leng < self.length):
            num_pad = self.length - leng
            dataset = dataset + [pad for j in range(num_pad)]

        dataset = np.array([dataset])
        leng = np.array([leng])

        score, output = self.sess.run([self.output, tf.argmax(self.output, 1)], feed_dict={self.image: dataset, self.L: leng, self.keep_prob: 1})

        if(max(score[0]) > 0.9):
            return output[0], max(score[0])
        else:
            return None, None