# Copyright 2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This component is for use with the OpenFlow tutorial.

It acts as a simple hub, but can be modified to act like an L2
learning switch.

It's roughly similar to the one Brandon Heller did for NOX.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
import sys
from pox.lib.addresses import IPAddr

log = core.getLogger()


class Tutorial (object):
    """
    A Tutorial object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """

    def __init__(self, connection):
        # Keep track of the connection to the switch so that we can
        # send it messages!
        self.connection = connection

        # This binds our PacketIn event listener
        connection.addListeners(self)

        # Use this table to keep track of which ethernet address is on
        # which switch port (keys are MACs, values are ports).
        self.mac_to_port = {}

        # Firewall
        self.firewall_rules = []
        self.set_firewall()

    def set_firewall(self):

        self.load_rules()

        if self.firewall_rules:
            for rule in self.firewall_rules:
                src_addr = rule[0]
                dst_addr = rule[1]
                port = rule[2]
                protocol = rule[3]

                firewall = of.ofp_match()
                firewall.dl_type = 0x0800
                if src_addr:
                    firewall.nw_src = IPAddr(src_addr)
                else:
                    src_addr = 'Any'
                if dst_addr:
                    firewall.nw_dst = IPAddr(dst_addr)
                else:
                    dst_addr = 'Any'
                if protocol:
                    if 'tcp' in protocol.lower():
                        firewall.nw_proto = 6
                    elif 'udp' in protocol.lower():
                        firewall.nw_proto = 17
                else:
                    protocol = 'Any'
                if port:
                    if protocol == 'Any':
                        protocol = 'TCP'
                        firewall.nw_proto = 6
                    firewall.tp_dst = int(port)
                else:
                    port = 'Any'
                msg = of.ofp_flow_mod()
                msg.match = firewall
                self.connection.send(msg)
                print('Firewall rule added: src addr: {} / dst addr: {} / in port: {} / protocol: {}'.format(
                    src_addr, dst_addr, port, protocol))

    def load_rules(self):
        try:
            with open('pox/misc/firewall.txt', 'r') as file:
                lines = file.readlines()
                for line in lines:
                    rules = line.split(',')
                    if len(rules) != 4:
                        print(
                            'WARNING! Invalid firewall rule detected! Continuing without firewall')
                        self.firewall_rules = None
                        return
                    rules = list(map(str.strip, rules))
                    if any(rules):
                        self.firewall_rules.append(rules)
        except:
            print(
                'WARNING! File "firewall.txt" not detected! Continuing without firewall')
            self.firewall_rules = None

    def resend_packet(self, packet_in, out_port):
        """
        Instructs the switch to resend a packet that it had sent to us.
        "packet_in" is the ofp_packet_in object the switch had sent to the
        controller due to a table-miss.
        """
        msg = of.ofp_packet_out()
        msg.data = packet_in

        # Add an action to send to the specified port
        action = of.ofp_action_output(port=out_port)
        msg.actions.append(action)

        # Send message to switch
        self.connection.send(msg)

    def act_like_hub(self, packet, packet_in):
        """
        Implement hub-like behavior -- send all packets to all ports besides
        the input port.
        """

        # We want to output to all ports -- we do that using the special
        # OFPP_ALL port as the output port.  (We could have also used
        # OFPP_FLOOD.)
        self.resend_packet(packet_in, of.OFPP_ALL)

        # Note that if we didn't get a valid buffer_id, a slightly better
        # implementation would check that we got the full data before
        # sending it (len(packet_in.data) should be == packet_in.total_len)).

    def act_like_switch(self, packet, packet_in):
        """
        Implement switch-like behavior.
        """

        # Here's some psuedocode to start you off implementing a learning
        # switch.  You'll need to rewrite it as real Python code.

        # Learn the port for the source MAC
        # self.mac_to_port ... <add or update entry>
        src_mac = str(packet.src)
        in_port = str(packet_in.in_port)
        self.mac_to_port[src_mac] = int(in_port)

        # if the port associated with the destination MAC of the packet is known:
        dst_mac = str(packet.dst)
        if dst_mac in self.mac_to_port:
            # Send packet out the associated port
            out_port = self.mac_to_port[dst_mac]
            self.resend_packet(packet_in, out_port)

            # Once you have the above working, try pushing a flow entry
            # instead of resending the packet (comment out the above and
            # uncomment and complete the below.)

            log.debug("Installing flow src: {}, dst: {}, port: {}".format(src_mac, dst_mac, out_port))
            # Maybe the log statement should have source/destination/port?

            msg = of.ofp_flow_mod()
            # Set fields to match received packet
            msg.match = of.ofp_match.from_packet(packet)
            #< Set other fields of flow_mod (timeouts? buffer_id?) >
            #< Add an output action, and send -- similar to resend_packet() >
            action = of.ofp_action_output(port=out_port)
            msg.actions.append(action)
            self.connection.send(msg)
        else:
            # Flood the packet out everything but the input port
            # This part looks familiar, right?
            self.resend_packet(packet_in, of.OFPP_ALL)

    def _handle_PacketIn(self, event):
        """
        Handles packet in messages from the switch.
        """

        packet = event.parsed  # This is the parsed packet data.
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        packet_in = event.ofp  # The actual ofp_packet_in message.

        # Comment out the following line and uncomment the one after
        # when starting the exercise.
        """
        self.act_like_hub(packet, packet_in)
        """
        self.act_like_switch(packet, packet_in)


def launch():
    """
    Starts the component
    """
    def start_switch(event):
        log.debug("Controlling %s" % (event.connection,))
        Tutorial(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
