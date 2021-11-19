#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade import quit_spade
from spade.message import Message
from spade.template import Template
from argparse import ArgumentParser
import pexpect
import json

from config import config

DBTYPES = config.keys()


class queryEngine():
    """Querying engine based on pexpect"""

    def __init__(self, initCommand: dict, valuesToExpect: list):
        self.valuesToExpect = valuesToExpect
        try:
            self.engine = pexpect.spawn(
                f"{initCommand.get('path')} {initCommand.get('args')}")
            self.expectingResults()
        except Exception as e:
            raise e

    def expectingResults(self):
        res = self.engine.expect(self.valuesToExpect)
        if res == 1:
            return f'Error occured: {self.engine.after}.'
            raise Exception(f'Error occured: {self.engine.after}.')
        else:
            print('Good to go.')
            return False

    def query(self, query: str):
        if query[-1] != ';':
            query = f'{query};'

        self.engine.sendline(query)
        return self.expectingResults()


class AgentClient(Agent):
    """Agent to be deployed and run on the student's system."""

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
            The metadata, if provided. Default `{}}`.

        Returns
        -------
        `True` if the message is sent, `False` otherwise.

        """
        try:
            msg = msg.make_reply()
            # msg.set_metadata('performative', 'reply')
            msg.body = reply

            metadata.update({
                'ontology': 'sparp'
            })

            for k, v in metadata.items():
                msg.set_metadata(k, v)

            await behav.send(msg)

            self.say(f'I have replied to {msg.to} with {msg}')

        except Exception as e:
            self.say(f'There was an error: {e}')

    class BehaviourContainer(FSMBehaviour):
        pass

    class ReceiveMessage(State):
        """Wait until a message is received."""
        async def run(self):
            self.agent.msg = None
            self.agent.msg = await self.receive(timeout=10)

            if self.agent.msg:
                # self.agent.say(self.agent.msg)
                self.set_next_state("AnalyseMessage")
            else:
                self.set_next_state("ReceiveMessage")

    class Die(State):
        """Kill the agent."""
        async def run(self):
            await self.agent.stop()

    class AnalyseMessage(State):
        """Analyse the received message and decide what to do with it."""
        async def run(self):
            body = json.loads(self.agent.msg.body)
            msg = self.agent.msg

            if body.get('engine') in DBTYPES:
                if msg.get_metadata('performative') == 'propose':
                    self.set_next_state('InitiateEngine')
                elif msg.get_metadata('performative') == 'request':
                    self.set_next_state('QueryEngine')
            elif msg.get_metadata('performative') == 'failure':
                self.set_next_state('Die')
            else:
                self.agent.say('Invalid metadata. Message ignored.')
                await self.agent.replyToMessage(
                    self,
                    msg,
                    'Invalid metadata. Message ignored.',
                    {
                        'performative': 'refuse'
                    }
                )
                self.set_next_state("ReceiveMessage")

    class InitiateEngine(State):
        """Initiate a data engine, based on the received message."""

        async def run(self):
            msg = self.agent.msg
            body = json.loads(msg.body)
            dbtype = body.get('engine')

            if not self.agent.engines.get(dbtype):
                try:
                    engine = queryEngine(
                        initCommand=config.get(dbtype).get('engine'),
                        valuesToExpect=config.get(dbtype).get('expectedValues')
                    )
                    self.agent.engines.update(
                        {
                            dbtype: engine
                        }
                    )
                except Exception:
                    pass

            if self.agent.engines.get(dbtype):
                await self.agent.replyToMessage(
                    self,
                    msg,
                    '',
                    {
                        'performative': 'accept-proposal'
                    }
                )
                self.set_next_state('ReceiveMessage')

            else:
                await self.agent.replyToMessage(
                    self,
                    msg,
                    '',
                    {
                        'performative': 'reject-proposal'
                    }
                )
                self.set_next_state('ReceiveMessage')

    class QueryEngine(State):
        """Execute query or statement using the designated engine."""
        async def run(self):
            msg = self.agent.msg
            body = json.loads(msg.body)
            dbtype = body.get('engine')
            engine = self.agent.engines.get(dbtype)

            if not engine:
                await self.agent.replyToMessage(
                    self,
                    msg,
                    '',
                    {
                        'performative': 'failure'
                    }
                )
                self.set_next_state('ReceiveMessage')
            else:
                try:
                    query = body.get('statement')
                    res = engine.query(
                        query
                    )
                    if res:
                        await self.agent.replyToMessage(
                            self,
                            msg,
                            json.dumps({'engine': dbtype, 'error': res}),
                            {
                                'performative': 'failure'
                            }
                        )
                    else:
                        await self.agent.replyToMessage(
                            self,
                            msg,
                            '',
                            {
                                'performative': 'inform'
                            }
                        )
                    self.set_next_state('ReceiveMessage')
                except Exception as e:
                    await self.agent.replyToMessage(
                        self,
                        msg,
                        str(e),
                        {
                            'performative': 'failure'
                        }
                    )
                    self.set_next_state('ReceiveMessage')

    class Register(State):
        """Register to the master agent."""
        async def run(self):
            msg = Message(to="sparp1@rec.foi.hr")
            msg.set_metadata('performative', 'subscribe')
            msg.set_metadata('ontology', 'sparp')
            msg.body = f"Hello, I'm {self.agent.name}."

            await self.send(msg)
            self.agent.say(f'Initial message sent!')

            self.set_next_state('ReceiveMessage')

    async def setup(self):
        self.engine = None
        self.engines = {type: None for type in DBTYPES}

        fsm = self.BehaviourContainer()

        fsm.add_state(name="Register", state=self.Register(), initial=True)
        fsm.add_state(name="ReceiveMessage", state=self.ReceiveMessage())
        fsm.add_state(name="AnalyseMessage", state=self.AnalyseMessage())
        fsm.add_state(name="Die", state=self.Die())
        fsm.add_state(name="InitiateEngine", state=self.InitiateEngine())
        fsm.add_state(name="QueryEngine", state=self.QueryEngine())

        fsm.add_transition(source="Register", dest="ReceiveMessage")
        fsm.add_transition(source="ReceiveMessage", dest="ReceiveMessage")
        fsm.add_transition(source="ReceiveMessage", dest="AnalyseMessage")
        fsm.add_transition(source="AnalyseMessage", dest="ReceiveMessage")
        fsm.add_transition(source="InitiateEngine", dest="ReceiveMessage")
        fsm.add_transition(source="QueryEngine", dest="ReceiveMessage")
        fsm.add_transition(source="AnalyseMessage", dest="Die")
        fsm.add_transition(source="AnalyseMessage", dest="QueryEngine")
        fsm.add_transition(source="AnalyseMessage", dest="InitiateEngine")

        template = Template()
        template.set_metadata('ontology', 'sparp')

        self.add_behaviour(fsm, template)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        "-jid",
        type=str,
        help="JID agenta",
        default=config.get('username'))
    parser.add_argument(
        "-pwd",
        type=str,
        help="Lozinka agenta",
        default=config.get('password'))
    args = parser.parse_args()

    agentKlijent = AgentClient(args.jid, args.pwd)
    pokretanje = agentKlijent.start()
    pokretanje.result()

    while agentKlijent.is_alive():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    agentKlijent.stop()
    quit_spade()
