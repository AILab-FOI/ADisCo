#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State, CyclicBehaviour
from spade import quit_spade
from spade.message import Message
from spade.template import Template
from argparse import ArgumentParser
from asyncio import sleep
import json


class AgentOne(Agent):
    """Agent to be run by the teacher."""

    def say(self, line: str):
        """Write `line` to the command line, with the agent's name.

        Parameters
        ----------
        line : str
            The string to be printed out.

        """
        print(f"{self.name}: {line}")

    async def replyToMessage(self, behav, msg: Message, reply: str, metadata: dict = {}):
        """Reply to a message.

        Parameters
        ----------
        msg : Message
            Message to be replied to.
        reply : str
            The contents of the reply.
        metadata : dict
            The metadata, if provided. Default `None`.

        Returns
        -------
        `True` if the message is sent, `False` otherwise.

        """
        try:
            msg = msg.make_reply()
            msg.body = reply

            metadata.update({
                'ontology': 'sparp'
            })

            for k, v in metadata.items():
                msg.set_metadata(k, v)

            await behav.send(msg)

            self.say(f'I have replied to {msg.to} with {msg}')
            return True

        except Exception as e:
            self.say(f'There was an error: {e}')
            return False

    class BehaviourContainer(FSMBehaviour):
        pass

    class Die(State):
        """Kill the agent."""
        async def run(self):
            await self.agent.stop()

    class AnalyseMessage(State):
        """Analyse the received message and decide what to do with it."""
        async def run(self):
            if self.agent.msgs:
                msg = self.agent.msgs[0]
                self.agent.say(f'I received {msg}')

                intent = msg.get_metadata('performative')

                if intent == 'request':
                    self.agent.command = json.loads(msg.body)
                    self.set_next_state('InitiateEngine')
                elif intent == 'reject-proposal':
                    counter = self.agent.clientCounters.get(msg.sender)
                    self.agent.clientCounters.update({
                        msg.sender: counter + 1
                    })
                    if counter < 6:
                        self.set_next_state('InitiateEngine')
                    else:
                        del self.agent.msgs[0]
                        self.set_next_state('AnalyseMessage')
                elif intent == 'accept-proposal':
                    self.set_next_state('DeliverCommand')
                elif intent == 'failure':
                    self.agent.say(f'Agent {msg.sender} failed with: {msg.body}')
                    del self.agent.msgs[0]
                    self.set_next_state('AnalyseMessage')
                elif intent == 'inform':
                    self.agent.say(f'Statement executed by {msg.sender}')
                    del self.agent.msgs[0]
                    self.set_next_state('AnalyseMessage')
                elif intent == 'refuse':
                    del self.agent.msgs[0]
                    self.set_next_state("AnalyseMessage")
                else:
                    self.agent.say('Invalid metadata. Message ignored.')
                    self.set_next_state('AnalyseMessage')

            else:
                await sleep(3)
                self.set_next_state('AnalyseMessage')

    class InitiateEngine(State):
        """Accept registrations."""
        async def run(self):
            msg = self.agent.msgs.pop(0)
            content = json.loads(msg.body)

            if content.get('target') == 'all':
                receivers = [str(client) for client in self.agent.clients]
            else:
                receivers = [content.get('target')]

            for receiver in receivers:
                msg = Message(
                    to=receiver,
                    body=json.dumps(content),
                    metadata={
                        'performative': 'propose',
                        'ontology': 'sparp'
                    }
                )
                self.agent.say(msg)
                await self.send(msg)

            self.set_next_state("AnalyseMessage")

    class DeliverCommand(State):
        """Deliver the received command after initialisation is confirmed."""
        async def run(self):
            msg = self.agent.msgs.pop(0)

            await self.agent.replyToMessage(
                self,
                msg,
                reply=json.dumps(self.agent.command),
                metadata={
                    'performative': 'request'
                }
            )

            self.set_next_state("AnalyseMessage")

    class Registration(CyclicBehaviour):
        """Accept registrations."""
        async def run(self):
            msg = None
            msg = await self.receive(timeout=10)

            if msg:
                self.agent.clients.append(msg.sender)
                self.agent.clientCounters.update({
                    msg.sender: 0
                })
                self.agent.say(self.agent.clients)

    class ReceiveMessages(CyclicBehaviour):
        async def run(self):
            msg = None
            msg = await self.receive(timeout=10)

            if msg:
                self.agent.msgs.append(msg)

    async def setup(self):
        self.clients = []
        self.msgs = []
        self.clientCounters = {}

        template1 = Template()
        template1.metadata = {
            'performative': 'subscribe'
        }
        self.add_behaviour(self.Registration(), template1)

        template2 = Template()
        template2.metadata = {
            'ontology': 'sparp',
        }
        self.add_behaviour(self.ReceiveMessages(), ~template1 & template2)

        fsm = self.BehaviourContainer()

        fsm.add_state(name="AnalyseMessage", state=self.AnalyseMessage(), initial=True)
        fsm.add_state(name="DeliverCommand", state=self.DeliverCommand())
        fsm.add_state(name="InitiateEngine", state=self.InitiateEngine())
        fsm.add_state(name="Die", state=self.Die())

        fsm.add_transition(source="AnalyseMessage", dest="DeliverCommand")
        fsm.add_transition(source="AnalyseMessage", dest="InitiateEngine")
        fsm.add_transition(source="AnalyseMessage", dest="Die")
        fsm.add_transition(source="AnalyseMessage", dest="AnalyseMessage")
        fsm.add_transition(source="DeliverCommand", dest="AnalyseMessage")
        fsm.add_transition(source="InitiateEngine", dest="AnalyseMessage")

        self.add_behaviour(fsm)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        "-jid",
        type=str,
        help="JID agenta",
        default='sparp1@rec.foi.hr')
    parser.add_argument(
        "-pwd",
        type=str,
        help="Lozinka agenta",
        default='Deluxe-Unclaimed-Facility1')
    args = parser.parse_args()

    agentKlijent = AgentOne(args.jid, args.pwd)
    pokretanje = agentKlijent.start()
    pokretanje.result()

    while agentKlijent.is_alive():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    agentKlijent.stop()
    quit_spade()
