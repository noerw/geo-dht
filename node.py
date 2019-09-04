# -*- coding: utf-8 -*-

from __future__ import division
from gevent import socket
from functools import partial
from keyspace import Keyspace
from hashlib import md5
import json
from traceback import print_exc

from topology import GridTopology, Direction

class Node(object):
    def __init__(self, own_port=None, keyspace=None):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.socket.bind(("localhost", own_port or 0))  # 0 Chooses random port
        self.port = self.socket.getsockname()[1]
        self.keyspace = keyspace
        self.hash = {}
        self.neighbours = GridTopology(keyspace)

        self.salt = 'asdndslkf' # TODO: should be proper randomized? must be shared among nodes? 🤔
        self.pepper = 'sdfjsdfoiwefslkf'

    def __str__(self):
        return "node:%s" % self.port

    def address(self):
        print ("I'm in address. self.port = %s" % self.port)
        return ('127.0.0.1', self.port)

    def join_network(self, entry_port):
        print ("Sending JOIN from %s to port %s." % (self, entry_port))
        self.sendto(("localhost", entry_port), "JOIN")

    def hash_key(self, key):
        return md5(key.encode('utf-8')).hexdigest()

    def key_to_keyspace(self, key):
        # keyspace is 2D -> split it
        hashX = self.hash_key(key + self.salt)
        hashY = self.hash_key(key + self.pepper)
        return (
            int(hashX, base=16) / (1 << 128), # convert to keyspace [0,1]
            int(hashY, base=16) / (1 << 128)
        )

    def sendto(self, address, message):
        if address:
            self.socket.sendto(message.encode('utf-8'), address)
        else:
            print (message)

    def query_others(self, query):
        point = self.key_to_keyspace(query.split()[1])
        address, keyspace = self.neighbours.getNeighbourForPoint(point)

        if address:
            self.sendto(address, query)
        else:
            print ('No neighbour found for %s', point)

    def query(self, query, sender=None):
        respond = partial(self.sendto, sender)

        # {
        #     "JOIN": commands.join,
        #     "STATE":
        # }

        if sender:
            print ("Received \"%s\" from %s." % (query, sender))

        try:
            if query == "JOIN":
                # TODO: join does not forward to other nodes (needs to provide a (random) point)
                # or should we allow a stateless GET, so the joining node finds the respective node prior to joining?

                # if point within own keyspace:
                    # subdivide keyspace
                    # send half of keyspace to new node
                    # inform affected neighbours
                    # update own neighbours
                # else
                    # route join request to neighbour closest to the point

                senderKeyspace, splitDirection = self.keyspace.subdivide()
                self.neighbours.addNeighbour(sender, senderKeyspace)

                respond("SETKEYSPACE %s" % json.dumps({
                    'keyspace': senderKeyspace.serialize(),
                    # FIXME: how the fuck should those be serialized?
                    # FIXME: should not include neighbours split direction (west / north), but ourselves instead!
                    'neighbours': self.neighbours.getNeighbours()
                }))

                # TODO: cleanup old neighbours in split direction (east / south)

                print ("Own keyspace is now %s" % self.keyspace)

            elif query.startswith("STATE"):
                print ("neighbours: %s" % self.neighbours)
                print ("hash: %s" % self.hash)
                print ("keyspace: %s" % self.keyspace)
                print ("port: %s" % self.port)

            elif query.startswith("SETKEYSPACE"):
                data = json.loads(query[12:])
                self.keyspace = Keyspace.unserialize(data['keyspace'])
                # TODO: initialize GridTopology with data['neighbours']
                self.neighbours = GridTopology(self.keyspace)

                # FIXME
                # self.sendto(self.right_address, "SET_ADDRESS %s" % json.dumps({
                #     'neighbor': 'left_address',
                #     'neighbor_address': self.address()
                # }))

            elif query.startswith("SET_ADDRESS"):
                # FIXME
                data = json.loads(query[12:])
                setattr(self, data['neighbor'], tuple(data['neighbor_address']))

            elif query.startswith("GET"):
                key = query.split()[1]
                point = self.key_to_keyspace(key)

                if point in self.keyspace:
                    try:
                        answer = "ANSWER %s" % self.hash[key]
                    except KeyError:
                        answer = "Key %s not found!" % key
                    respond(answer)
                else:
                    self.query_others(query)

            elif query.startswith("PUT"):
                _, key, value = query.split()
                point = self.key_to_keyspace(key)

                if point in self.keyspace:
                    self.hash[key] = value
                    print ("Own hash is now %s" % self.hash)
                    respond("ANSWER Successfully PUT { %s: %s }." % (key, value))
                else:
                    self.query_others(query)

            elif query.startswith("ANSWER"):
                print ("ANSWER: %s." % query.lstrip("ANSWER "))

            elif query == '':
                pass

            else:
                print ("Unrecognized query \"%s\"." % query)

        except Exception as err:
            print_exc()

'''
# z-order <-> binary tree relationship
- until 4 bits: one neighbour in each branch, going one level up each
-

# z-order <-> de-briujn

'''
