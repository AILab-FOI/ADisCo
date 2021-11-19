#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade import quit_spade
from spade.message import Message
from argparse import ArgumentParser
import json

from messages import MESSAGES

CHOSEN_MESSAGE = 'mongoInsertData'


class AgentCommander(Agent):
    """Agent to be run by the teacher."""

    def say(self, line: str):
        """Write `line` to the command line, with the agent's name.

        Parameters
        ----------
        line : str
            The string to be printed out.

        """
        print(f"{self.name}: {line}")

    class SendCommand(OneShotBehaviour):
        """Send command message."""
        async def run(self):
            msg = Message(to="sparp1@rec.foi.hr")
            msg.set_metadata('performative', 'request')
            msg.set_metadata('ontology', 'sparp')

            msg.body = json.dumps(MESSAGES.get(CHOSEN_MESSAGE))

            await self.send(msg)
            self.agent.say(f'Command message sent!')

        async def on_end(self):
            await self.agent.stop()

    async def setup(self):
        behav = self.SendCommand()
        self.add_behaviour(behav)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        "-jid",
        type=str,
        help="JID agenta",
        default='agent@rec.foi.hr')
    parser.add_argument(
        "-pwd",
        type=str,
        help="Lozinka agenta",
        default='tajna')
    args = parser.parse_args()

    agent = AgentCommander(args.jid, args.pwd)
    pokretanje = agent.start()
    pokretanje.result()

    while agent.is_alive():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break
    quit_spade()
