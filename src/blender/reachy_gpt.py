import json
import os
from requests.exceptions import RequestException

import bpy
import openai


class ReachyGPT:

    def __init__(self):

        self.client = None
        self.chat_history = []

        self.gpt_model = "gpt-4o"
        self.max_tokens = 1000
        self.chat_history_len = 5

        self.action_catalouge = [
            "ReachyWave",
            "ReachyDance",
            "ReachyYes",
            "ReachyNo",
            "ReachyShrug",
        ]

        self.system_prompt = """"
            You are a humanoid robot named Reachy. You can emote using the actions ReachyWave, ReachyDance, ReachyYes, ReachyNo, and ReachyShrug.

            - Respond to user input with a text response and the most appropriate action's name
            - If no other action is more appropriate, use ReachyShrug
            - Please format your response as JSON with two keys: "action" and "answer"

            Example:

            user: Hello Reachy
            assistant: {"action": "ReachyWave", "answer": "Hej! Hvordan kan jeg hjælpe?"}
            """

    def activate(self, report_blender):

        if not os.getenv("OPENAI_API_KEY"):
            report_blender(
                {"ERROR"},
                "No API key detected. Please write API key to OPENAI_API_KEY environment variable. System restart may be required after writing to environment variable.",
            )
            return False

        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        return True

    def get_gpt_response(self, messages, report_blender):

        try:
            # Request response from ChatGPT
            response = self.client.chat.completions.create(
                model=self.gpt_model,
                messages=messages,
                max_tokens=self.max_tokens,
            )

            if hasattr(response, "choices") and len(response.choices) > 0:
                message = json.loads(response.choices[0].message.content)

                if "action" not in message and "answer" not in message:
                    report_blender(
                        {"ERROR"}, "Message not formatted correctly: " + str(message)
                    )
                    return "Sorry, I couldn't generate a response."

                return message

            else:
                report_blender({"ERROR"}, "No completion choices returned.")
                return "Sorry, I couldn't generate a response."

        except openai.OpenAIError as error:
            report_blender({"ERROR"}, "OpenAI API error: " + str(error))
            return "Sorry, there was an error with the AI service."

        except RequestException as e:
            report_blender({"ERROR"}, "Request error: " + str(error))
            return "Sorry, there was a network issue."

        except Exception as error:
            report_blender({"ERROR"}, "Could not send response: " + str(error))
            return "Sorry, something went wrong."

    def send_request(self, promt, reachy_object, report_blender):

        response = {"action": "", "answer": ""}  # Mock response

        if len(promt) == 0:
            report_blender({"ERROR"}, "Please provide a promt.")
            return response

        if not self.client:
            report_blender(
                {"ERROR"}, "No OpenAI client detected. Please activate client."
            )
            return response

        # Add system promt and recent chat history
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.chat_history[-self.chat_history_len :])

        # Add user promt
        message_user = {"role": "user", "content": promt}
        messages.append(message_user)
        self.chat_history.append(message_user)

        # Get response from ChatGPT, and send action / animation to Reachy
        response = self.get_gpt_response(messages, report_blender)

        if response["action"] not in self.action_catalouge:
            report_blender(
                {"ERROR"}, "Response was not an action: " + response["action"]
            )
            response["action"] = "ReachyShrug"

        report_blender({"INFO"}, "Chosen action: " + response["action"])
        report_blender({"INFO"}, response["answer"])

        bpy.context.object.animation_data.action = bpy.data.actions.get(
            response["action"]
        )

        if reachy_object.reachy != None:
            # Send action to Reachy robot
            reachy_object.animate_angles(report_blender)

        else:
            report_blender({"INFO"}, "Reachy not connected, playing animation instead.")

            # Play animation
            bpy.ops.screen.animation_cancel()
            bpy.ops.screen.frame_jump()
            bpy.ops.screen.animation_play()

        return response
