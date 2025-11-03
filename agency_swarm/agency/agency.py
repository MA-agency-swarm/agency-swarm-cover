import inspect
import json
import os
import queue
import re
import threading
import uuid
from collections import deque
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

from dotenv import load_dotenv
from openai.lib._parsing._completions import type_to_response_format_param
from openai.types.beta.threads import Message
from openai.types.beta.threads.runs import RunStep
from openai.types.beta.threads.runs.tool_call import (
    CodeInterpreterToolCall,
    FileSearchToolCall,
    FunctionToolCall,
    ToolCall,
)
from pydantic import BaseModel, Field, field_validator, model_validator
from ragflow_sdk import Chat, DataSet, RAGFlow
from rich.console import Console
from typing_extensions import override

from agency_swarm.agents import Agent
from agency_swarm.messages import MessageOutput
from agency_swarm.messages.message_output import MessageOutputLive
from agency_swarm.threads import Thread
from agency_swarm.threads.thread_async import ThreadAsync
from agency_swarm.tools import BaseTool, CodeInterpreter, FileSearch
from agency_swarm.tools.send_message import SendMessage, SendMessageBase
from agency_swarm.user import User
from agency_swarm.util.errors import RefusalError
from agency_swarm.util.files import get_file_purpose, get_tools
from agency_swarm.util.shared_state import SharedState
from agency_swarm.util.streaming import AgencyEventHandler

console = Console()

T = TypeVar("T", bound=BaseModel)


class SettingsCallbacks(TypedDict):
    load: Callable[[], List[Dict]]
    save: Callable[[List[Dict]], Any]


class ThreadsCallbacks(TypedDict):
    load: Callable[[], Dict]
    save: Callable[[Dict], Any]


class Agency:
    def __init__(
        self,
        agency_chart: List,
        thread_strategy: Dict[Literal["always_same", "always_new"], List[Tuple]] = {},
        shared_instructions: str = "",
        shared_files: Union[str, List[str]] = None,
        async_mode: Literal["threading", "tools_threading"] = None,
        send_message_tool_class: Type[SendMessageBase] = SendMessage,
        settings_path: str = "./settings.json",
        settings_callbacks: SettingsCallbacks = None,
        threads_callbacks: ThreadsCallbacks = None,
        temperature: float = 0.3,
        top_p: float = 1.0,
        max_prompt_tokens: int = None,
        max_completion_tokens: int = None,
        truncation_strategy: dict = None,
        log_file=None,
    ):
        """
        Initializes the Agency object, setting up agents, threads, and core functionalities.

        Parameters:
            agency_chart: The structure defining the hierarchy and interaction of agents within the agency.
            thread_strategy (Dict[Literal["always_same", "always_new"], List[Tuple]], optional): The strategy used for retrieving threads when starting a new conversation. Defaults to "always_same".
            shared_instructions (str, optional): A path to a file containing shared instructions for all agents. Defaults to an empty string.
            shared_files (Union[str, List[str]], optional): A path to a folder or a list of folders containing shared files for all agents. Defaults to None.
            async_mode (str, optional): Specifies the mode for asynchronous processing. In "threading" mode, all sub-agents run in separate threads. In "tools_threading" mode, all tools run in separate threads, but agents do not. Defaults to None.
            send_message_tool_class (Type[SendMessageBase], optional): The class to use for the send_message tool. For async communication, use `SendMessageAsyncThreading`. Defaults to SendMessage.
            settings_path (str, optional): The path to the settings file for the agency. Must be json. If file does not exist, it will be created. Defaults to None.
            settings_callbacks (SettingsCallbacks, optional): A dictionary containing functions to load and save settings for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            threads_callbacks (ThreadsCallbacks, optional): A dictionary containing functions to load and save threads for the agency. The keys must be "load" and "save". Both values must be defined. Defaults to None.
            temperature (float, optional): The temperature value to use for the agents. Agent-specific values will override this. Defaults to 0.3.
            top_p (float, optional): The top_p value to use for the agents. Agent-specific values will override this. Defaults to None.
            max_prompt_tokens (int, optional): The maximum number of tokens allowed in the prompt for each agent. Agent-specific values will override this. Defaults to None.
            max_completion_tokens (int, optional): The maximum number of tokens allowed in the completion for each agent. Agent-specific values will override this. Defaults to None.
            truncation_strategy (dict, optional): The truncation strategy to use for the completion for each agent. Agent-specific values will override this. Defaults to None.

        This constructor initializes various components of the Agency, including CEO, agents, threads, and user interactions. It parses the agency chart to set up the organizational structure and initializes the messaging tools, agents, and threads necessary for the operation of the agency. Additionally, it prepares a main thread for user interactions.
        """
        self.ceo = None
        self.user = User()
        self.agents = []
        self.agents_and_threads = {}
        self.main_recipients = []
        self.main_thread = None
        self.recipient_agents = None  # for autocomplete
        self.thread_strategy = thread_strategy
        self.shared_files = shared_files if shared_files else []
        self.async_mode = async_mode
        self.send_message_tool_class = send_message_tool_class
        self.settings_path = settings_path
        self.settings_callbacks = settings_callbacks
        self.threads_callbacks = threads_callbacks
        self.temperature = temperature
        self.top_p = top_p
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy
        self.log_file = log_file

        # set thread type based send_message_tool_class async mode
        if (
            hasattr(send_message_tool_class.ToolConfig, "async_mode")
            and send_message_tool_class.ToolConfig.async_mode
        ):
            self._thread_type = ThreadAsync
        else:
            self._thread_type = Thread

        if self.async_mode == "threading":
            from agency_swarm.tools.send_message import SendMessageAsyncThreading

            print(
                "Warning: 'threading' mode is deprecated. Please use send_message_tool_class = SendMessageAsyncThreading to use async communication."
            )
            self.send_message_tool_class = SendMessageAsyncThreading
        elif self.async_mode == "tools_threading":
            Thread.async_mode = "tools_threading"
            print(
                "Warning: 'tools_threading' mode is deprecated. Use tool.ToolConfig.async_mode = 'threading' instead."
            )
        elif self.async_mode is None:
            pass
        else:
            raise Exception(
                "Please select async_mode = 'threading' or 'tools_threading'."
            )

        if os.path.isfile(
            os.path.join(self._get_class_folder_path(), shared_instructions)
        ):
            self._read_instructions(
                os.path.join(self._get_class_folder_path(), shared_instructions)
            )
        elif os.path.isfile(shared_instructions):
            self._read_instructions(shared_instructions)
        else:
            self.shared_instructions = shared_instructions

        self.shared_state = SharedState()

        self._parse_agency_chart(agency_chart)
        self._init_threads()
        self._create_special_tools()
        self._init_agents()

    def get_completion(
        self,
        message: str,
        message_files: List[str] = None,
        yield_messages: bool = False,
        recipient_agent: Agent = None,
        additional_instructions: str = None,
        attachments: List[dict] = None,
        tool_choice: dict = None,
        verbose: bool = False,
        response_format: dict = None,
    ):
        """
        Retrieves the completion for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            yield_messages (bool, optional): Flag to determine if intermediate messages should be yielded. Defaults to True.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.
            response_format (dict, optional): The response format to use for the completion.

        Returns:
            Generator or final response: Depending on the 'yield_messages' flag, this method returns either a generator yielding intermediate messages or the final response from the main thread.
        """
        if verbose and yield_messages:
            raise Exception("Verbose mode is not compatible with yield_messages=True")

        res = self.main_thread.get_completion(
            message=message,
            message_files=message_files,
            attachments=attachments,
            recipient_agent=recipient_agent,
            additional_instructions=additional_instructions,
            tool_choice=tool_choice,
            yield_messages=yield_messages or verbose,
            response_format=response_format,
        )

        if not yield_messages or verbose:
            while True:
                try:
                    message = next(res)
                    if verbose:
                        message.cprint()
                except StopIteration as e:
                    return e.value

        return res

    def get_completion_stream(
        self,
        message: str,
        event_handler: type(AgencyEventHandler),
        message_files: List[str] = None,
        recipient_agent: Agent = None,
        additional_instructions: str = None,
        attachments: List[dict] = None,
        tool_choice: dict = None,
        response_format: dict = None,
    ):
        """
        Generates a stream of completions for a given message from the main thread.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            event_handler (type(AgencyEventHandler)): The event handler class to handle the completion stream. https://github.com/openai/openai-python/blob/main/helpers.md
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            parallel_tool_calls (bool, optional): Whether to enable parallel function calling during tool use. Defaults to True.

        Returns:
            Final response: Final response from the main thread.
        """
        if not inspect.isclass(event_handler):
            raise Exception("Event handler must not be an instance.")

        res = self.main_thread.get_completion_stream(
            message=message,
            message_files=message_files,
            event_handler=event_handler,
            attachments=attachments,
            recipient_agent=recipient_agent,
            additional_instructions=additional_instructions,
            tool_choice=tool_choice,
            response_format=response_format,
        )

        while True:
            try:
                next(res)
            except StopIteration as e:
                event_handler.on_all_streams_end()

                return e.value

    def get_completion_parse(
        self,
        message: str,
        response_format: Type[T],
        message_files: List[str] = None,
        recipient_agent: Agent = None,
        additional_instructions: str = None,
        attachments: List[dict] = None,
        tool_choice: dict = None,
        verbose: bool = False,
    ) -> T:
        """
        Retrieves the completion for a given message from the main thread and parses the response using the provided pydantic model.

        Parameters:
            message (str): The message for which completion is to be retrieved.
            response_format (type(BaseModel)): The response format to use for the completion.
            message_files (list, optional): A list of file ids to be sent as attachments with the message. When using this parameter, files will be assigned both to file_search and code_interpreter tools if available. It is recommended to assign files to the most sutiable tool manually, using the attachments parameter.  Defaults to None.
            recipient_agent (Agent, optional): The agent to which the message should be sent. Defaults to the first agent in the agency chart.
            additional_instructions (str, optional): Additional instructions to be sent with the message. Defaults to None.
            attachments (List[dict], optional): A list of attachments to be sent with the message, following openai format. Defaults to None.
            tool_choice (dict, optional): The tool choice for the recipient agent to use. Defaults to None.
            verbose (bool, optional): Whether to print the intermediary messages in console. Defaults to False.

        Returns:
            Final response: The final response from the main thread, parsed using the provided pydantic model.
        """
        response_model = None
        if isinstance(response_format, type):
            response_model = response_format
            response_format = type_to_response_format_param(response_format)

        res = self.get_completion(
            message=message,
            message_files=message_files,
            recipient_agent=recipient_agent,
            additional_instructions=additional_instructions,
            attachments=attachments,
            tool_choice=tool_choice,
            response_format=response_format,
            verbose=verbose,
        )

        try:
            return response_model.model_validate_json(res)
        except:
            parsed_res = json.loads(res)
            if "refusal" in parsed_res:
                raise RefusalError(parsed_res["refusal"])
            else:
                raise Exception("Failed to parse response: " + res)

    def demo_gradio(self, height=450, dark_mode=True, **kwargs):
        """
        Launches a Gradio-based demo interface for the agency chatbot.

        Parameters:
            height (int, optional): The height of the chatbot widget in the Gradio interface. Default is 600.
            dark_mode (bool, optional): Flag to determine if the interface should be displayed in dark mode. Default is True.
            **kwargs: Additional keyword arguments to be passed to the Gradio interface.
        This method sets up and runs a Gradio interface, allowing users to interact with the agency's chatbot. It includes a text input for the user's messages and a chatbot interface for displaying the conversation. The method handles user input and chatbot responses, updating the interface dynamically.
        """

        try:
            import gradio as gr
        except ImportError:
            raise Exception("Please install gradio: pip install gradio")

        js = """function () {
          gradioURL = window.location.href
          if (!gradioURL.endsWith('?__theme={theme}')) {
            window.location.replace(gradioURL + '?__theme={theme}');
          }
        }"""

        if dark_mode:
            js = js.replace("{theme}", "dark")
        else:
            js = js.replace("{theme}", "light")

        attachments = []
        images = []
        message_file_names = None
        uploading_files = False
        recipient_agent_names = [agent.name for agent in self.main_recipients]
        recipient_agent = self.main_recipients[0]

        with gr.Blocks(js=js) as demo:
            chatbot_queue = queue.Queue()
            chatbot = gr.Chatbot(height=height)
            with gr.Row():
                with gr.Column(scale=9):
                    dropdown = gr.Dropdown(
                        label="Recipient Agent",
                        choices=recipient_agent_names,
                        value=recipient_agent.name,
                    )
                    msg = gr.Textbox(label="Your Message", lines=4)
                with gr.Column(scale=1):
                    file_upload = gr.Files(label="OpenAI Files", type="filepath")
            button = gr.Button(value="Send", variant="primary")

            def handle_dropdown_change(selected_option):
                nonlocal recipient_agent
                recipient_agent = self._get_agent_by_name(selected_option)

            def handle_file_upload(file_list):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                uploading_files = True
                attachments = []
                message_file_names = []
                if file_list:
                    try:
                        for file_obj in file_list:
                            purpose = get_file_purpose(file_obj.name)

                            with open(file_obj.name, "rb") as f:
                                # Upload the file to OpenAI
                                file = self.main_thread.client.files.create(
                                    file=f, purpose=purpose
                                )

                            if purpose == "vision":
                                images.append(
                                    {
                                        "type": "image_file",
                                        "image_file": {"file_id": file.id},
                                    }
                                )
                            else:
                                attachments.append(
                                    {
                                        "file_id": file.id,
                                        "tools": get_tools(file.filename),
                                    }
                                )

                            message_file_names.append(file.filename)
                            print(f"Uploaded file ID: {file.id}")
                        return attachments
                    except Exception as e:
                        print(f"Error: {e}")
                        return str(e)
                    finally:
                        uploading_files = False

                uploading_files = False
                return "No files uploaded"

            def user(user_message, history):
                if not user_message.strip():
                    return user_message, history

                nonlocal message_file_names
                nonlocal uploading_files
                nonlocal images
                nonlocal attachments
                nonlocal recipient_agent

                # Check if attachments contain file search or code interpreter types
                def check_and_add_tools_in_attachments(attachments, recipient_agent):
                    for attachment in attachments:
                        for tool in attachment.get("tools", []):
                            if tool["type"] == "file_search":
                                if not any(
                                    isinstance(t, FileSearch)
                                    for t in recipient_agent.tools
                                ):
                                    # Add FileSearch tool if it does not exist
                                    recipient_agent.tools.append(FileSearch)
                                    recipient_agent.client.beta.assistants.update(
                                        recipient_agent.id,
                                        tools=recipient_agent.get_oai_tools(),
                                    )
                                    print(
                                        "Added FileSearch tool to recipient agent to analyze the file."
                                    )
                            elif tool["type"] == "code_interpreter":
                                if not any(
                                    isinstance(t, CodeInterpreter)
                                    for t in recipient_agent.tools
                                ):
                                    # Add CodeInterpreter tool if it does not exist
                                    recipient_agent.tools.append(CodeInterpreter)
                                    recipient_agent.client.beta.assistants.update(
                                        recipient_agent.id,
                                        tools=recipient_agent.get_oai_tools(),
                                    )
                                    print(
                                        "Added CodeInterpreter tool to recipient agent to analyze the file."
                                    )
                    return None

                check_and_add_tools_in_attachments(attachments, recipient_agent)

                if history is None:
                    history = []

                original_user_message = user_message

                # Append the user message with a placeholder for bot response
                if recipient_agent:
                    user_message = (
                        f"👤 User 🗣️ @{recipient_agent.name}:\n" + user_message.strip()
                    )
                else:
                    user_message = f"👤 User:" + user_message.strip()

                nonlocal message_file_names
                if message_file_names:
                    user_message += "\n\n📎 Files:\n" + "\n".join(message_file_names)

                return original_user_message, history + [[user_message, None]]

            class GradioEventHandler(AgencyEventHandler):
                message_output = None

                @classmethod
                def change_recipient_agent(cls, recipient_agent_name):
                    nonlocal chatbot_queue
                    chatbot_queue.put("[change_recipient_agent]")
                    chatbot_queue.put(recipient_agent_name)

                @override
                def on_message_created(self, message: Message) -> None:
                    if message.role == "user":
                        full_content = ""
                        for content in message.content:
                            if content.type == "image_file":
                                full_content += (
                                    f"🖼️ Image File: {content.image_file.file_id}\n"
                                )
                                continue

                            if content.type == "image_url":
                                full_content += f"\n{content.image_url.url}\n"
                                continue

                            if content.type == "text":
                                full_content += content.text.value + "\n"

                        self.message_output = MessageOutput(
                            "text",
                            self.agent_name,
                            self.recipient_agent_name,
                            full_content,
                        )

                    else:
                        self.message_output = MessageOutput(
                            "text", self.recipient_agent_name, self.agent_name, ""
                        )

                    chatbot_queue.put("[new_message]")
                    chatbot_queue.put(self.message_output.get_formatted_content())

                @override
                def on_text_delta(self, delta, snapshot):
                    chatbot_queue.put(delta.value)

                @override
                def on_tool_call_created(self, tool_call: ToolCall):
                    if isinstance(tool_call, dict):
                        if "type" not in tool_call:
                            tool_call["type"] = "function"

                        if tool_call["type"] == "function":
                            tool_call = FunctionToolCall(**tool_call)
                        elif tool_call["type"] == "code_interpreter":
                            tool_call = CodeInterpreterToolCall(**tool_call)
                        elif (
                            tool_call["type"] == "file_search"
                            or tool_call["type"] == "retrieval"
                        ):
                            tool_call = FileSearchToolCall(**tool_call)
                        else:
                            raise ValueError(
                                "Invalid tool call type: " + tool_call["type"]
                            )

                    # TODO: add support for code interpreter and retrieval tools
                    if tool_call.type == "function":
                        chatbot_queue.put("[new_message]")
                        self.message_output = MessageOutput(
                            "function",
                            self.recipient_agent_name,
                            self.agent_name,
                            str(tool_call.function),
                        )
                        chatbot_queue.put(
                            self.message_output.get_formatted_header() + "\n"
                        )

                @override
                def on_tool_call_done(self, snapshot: ToolCall):
                    if isinstance(snapshot, dict):
                        if "type" not in snapshot:
                            snapshot["type"] = "function"

                        if snapshot["type"] == "function":
                            snapshot = FunctionToolCall(**snapshot)
                        elif snapshot["type"] == "code_interpreter":
                            snapshot = CodeInterpreterToolCall(**snapshot)
                        elif snapshot["type"] == "file_search":
                            snapshot = FileSearchToolCall(**snapshot)
                        else:
                            raise ValueError(
                                "Invalid tool call type: " + snapshot["type"]
                            )

                    self.message_output = None

                    # TODO: add support for code interpreter and retrieval tools
                    if snapshot.type != "function":
                        return

                    chatbot_queue.put(str(snapshot.function))

                    if snapshot.function.name == "SendMessage":
                        try:
                            args = eval(snapshot.function.arguments)
                            recipient = args["recipient"]
                            self.message_output = MessageOutput(
                                "text",
                                self.recipient_agent_name,
                                recipient,
                                args["message"],
                            )

                            chatbot_queue.put("[new_message]")
                            chatbot_queue.put(
                                self.message_output.get_formatted_content()
                            )
                        except Exception as e:
                            pass

                    self.message_output = None

                @override
                def on_run_step_done(self, run_step: RunStep) -> None:
                    if run_step.type == "tool_calls":
                        for tool_call in run_step.step_details.tool_calls:
                            if tool_call.type != "function":
                                continue

                            if tool_call.function.name == "SendMessage":
                                continue

                            self.message_output = None
                            chatbot_queue.put("[new_message]")

                            self.message_output = MessageOutput(
                                "function_output",
                                tool_call.function.name,
                                self.recipient_agent_name,
                                tool_call.function.output,
                            )

                            chatbot_queue.put(
                                self.message_output.get_formatted_header() + "\n"
                            )
                            chatbot_queue.put(tool_call.function.output)

                @override
                @classmethod
                def on_all_streams_end(cls):
                    cls.message_output = None
                    chatbot_queue.put("[end]")

            def bot(original_message, history, dropdown):
                nonlocal attachments
                nonlocal message_file_names
                nonlocal recipient_agent
                nonlocal recipient_agent_names
                nonlocal images
                nonlocal uploading_files

                if not original_message:
                    return (
                        "",
                        history,
                        gr.update(
                            value=recipient_agent.name,
                            choices=set([*recipient_agent_names, recipient_agent.name]),
                        ),
                    )

                if uploading_files:
                    history.append([None, "Uploading files... Please wait."])
                    yield (
                        "",
                        history,
                        gr.update(
                            value=recipient_agent.name,
                            choices=set([*recipient_agent_names, recipient_agent.name]),
                        ),
                    )
                    return (
                        "",
                        history,
                        gr.update(
                            value=recipient_agent.name,
                            choices=set([*recipient_agent_names, recipient_agent.name]),
                        ),
                    )

                print("Message files: ", attachments)
                print("Images: ", images)

                if images and len(images) > 0:
                    original_message = [
                        {
                            "type": "text",
                            "text": original_message,
                        },
                        *images,
                    ]

                completion_thread = threading.Thread(
                    target=self.get_completion_stream,
                    args=(
                        original_message,
                        GradioEventHandler,
                        [],
                        recipient_agent,
                        "",
                        attachments,
                        None,
                    ),
                )
                completion_thread.start()

                attachments = []
                message_file_names = []
                images = []
                uploading_files = False

                new_message = True
                while True:
                    try:
                        bot_message = chatbot_queue.get(block=True)

                        if bot_message == "[end]":
                            completion_thread.join()
                            break

                        if bot_message == "[new_message]":
                            new_message = True
                            continue

                        if bot_message == "[change_recipient_agent]":
                            new_agent_name = chatbot_queue.get(block=True)
                            recipient_agent = self._get_agent_by_name(new_agent_name)
                            yield (
                                "",
                                history,
                                gr.update(
                                    value=new_agent_name,
                                    choices=set(
                                        [*recipient_agent_names, recipient_agent.name]
                                    ),
                                ),
                            )
                            continue

                        if new_message:
                            history.append([None, bot_message])
                            new_message = False
                        else:
                            history[-1][1] += bot_message

                        yield (
                            "",
                            history,
                            gr.update(
                                value=recipient_agent.name,
                                choices=set(
                                    [*recipient_agent_names, recipient_agent.name]
                                ),
                            ),
                        )
                    except queue.Empty:
                        break

            button.click(user, inputs=[msg, chatbot], outputs=[msg, chatbot]).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )
            dropdown.change(handle_dropdown_change, dropdown)
            file_upload.change(handle_file_upload, file_upload)
            msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
                bot, [msg, chatbot, dropdown], [msg, chatbot, dropdown]
            )

            # Enable queuing for streaming intermediate outputs
            demo.queue(default_concurrency_limit=10)

        # Launch the demo
        demo.launch(**kwargs)
        return demo

    def _recipient_agent_completer(self, text, state):
        """
        Autocomplete completer for recipient agent names.
        """
        options = [
            agent
            for agent in self.recipient_agents
            if agent.lower().startswith(text.lower())
        ]
        if state < len(options):
            return options[state]
        else:
            return None

    def _setup_autocomplete(self):
        """
        Sets up readline with the completer function.
        """
        try:
            import readline
        except ImportError:
            # Attempt to import pyreadline for Windows compatibility
            try:
                import pyreadline as readline
            except ImportError:
                print(
                    "Module 'readline' not found. Autocomplete will not work. If you are using Windows, try installing 'pyreadline3'."
                )
                return

        if not readline:
            return

        try:
            readline.set_completer(self._recipient_agent_completer)
            readline.parse_and_bind("tab: complete")
        except Exception as e:
            print(
                f"Error setting up autocomplete for agents in terminal: {e}. Autocomplete will not work."
            )

    def run_demo(self):
        """
        Executes agency in the terminal with autocomplete for recipient agent names.
        """
        outer_self = self
        from agency_swarm import AgencyEventHandler

        class TermEventHandler(AgencyEventHandler):
            message_output = None

            @override
            def on_message_created(self, message: Message) -> None:
                if message.role == "user":
                    self.message_output = MessageOutputLive(
                        "text", self.agent_name, self.recipient_agent_name, ""
                    )
                    self.message_output.cprint_update(message.content[0].text.value)
                else:
                    self.message_output = MessageOutputLive(
                        "text", self.recipient_agent_name, self.agent_name, ""
                    )

            @override
            def on_message_done(self, message: Message) -> None:
                self.message_output = None

            @override
            def on_text_delta(self, delta, snapshot):
                self.message_output.cprint_update(snapshot.value)

            @override
            def on_tool_call_created(self, tool_call):
                if isinstance(tool_call, dict):
                    if "type" not in tool_call:
                        tool_call["type"] = "function"

                    if tool_call["type"] == "function":
                        tool_call = FunctionToolCall(**tool_call)
                    elif tool_call["type"] == "code_interpreter":
                        tool_call = CodeInterpreterToolCall(**tool_call)
                    elif (
                        tool_call["type"] == "file_search"
                        or tool_call["type"] == "retrieval"
                    ):
                        tool_call = FileSearchToolCall(**tool_call)
                    else:
                        raise ValueError("Invalid tool call type: " + tool_call["type"])

                # TODO: add support for code interpreter and retirieval tools

                if tool_call.type == "function":
                    self.message_output = MessageOutputLive(
                        "function",
                        self.recipient_agent_name,
                        self.agent_name,
                        str(tool_call.function),
                    )

            @override
            def on_tool_call_delta(self, delta, snapshot):
                if isinstance(snapshot, dict):
                    if "type" not in snapshot:
                        snapshot["type"] = "function"

                    if snapshot["type"] == "function":
                        snapshot = FunctionToolCall(**snapshot)
                    elif snapshot["type"] == "code_interpreter":
                        snapshot = CodeInterpreterToolCall(**snapshot)
                    elif snapshot["type"] == "file_search":
                        snapshot = FileSearchToolCall(**snapshot)
                    else:
                        raise ValueError("Invalid tool call type: " + snapshot["type"])

                self.message_output.cprint_update(str(snapshot.function))

            @override
            def on_tool_call_done(self, snapshot):
                self.message_output = None

                # TODO: add support for code interpreter and retrieval tools
                if snapshot.type != "function":
                    return

                if snapshot.function.name == "SendMessage" and not (
                    hasattr(
                        outer_self.send_message_tool_class.ToolConfig,
                        "output_as_result",
                    )
                    and outer_self.send_message_tool_class.ToolConfig.output_as_result
                ):
                    try:
                        args = eval(snapshot.function.arguments)
                        recipient = args["recipient"]
                        self.message_output = MessageOutputLive(
                            "text", self.recipient_agent_name, recipient, ""
                        )

                        self.message_output.cprint_update(args["message"])
                    except Exception as e:
                        pass

                self.message_output = None

            @override
            def on_run_step_done(self, run_step: RunStep) -> None:
                if run_step.type == "tool_calls":
                    for tool_call in run_step.step_details.tool_calls:
                        if tool_call.type != "function":
                            continue

                        if tool_call.function.name == "SendMessage":
                            continue

                        self.message_output = None
                        self.message_output = MessageOutputLive(
                            "function_output",
                            tool_call.function.name,
                            self.recipient_agent_name,
                            tool_call.function.output,
                        )
                        self.message_output.cprint_update(tool_call.function.output)

                    self.message_output = None

            @override
            def on_end(self):
                self.message_output = None

        self.recipient_agents = [str(agent.name) for agent in self.main_recipients]

        self._setup_autocomplete()  # Prepare readline for autocomplete

        while True:
            console.rule()
            text = input("👤 USER: ")

            if not text:
                continue

            if text.lower() == "exit":
                break

            recipient_agent = None
            if "@" in text:
                recipient_agent = text.split("@")[1].split(" ")[0]
                text = text.replace(f"@{recipient_agent}", "").strip()
                try:
                    recipient_agent = [
                        agent
                        for agent in self.recipient_agents
                        if agent.lower() == recipient_agent.lower()
                    ][0]
                    recipient_agent = self._get_agent_by_name(recipient_agent)
                except Exception as e:
                    print(f"Recipient agent {recipient_agent} not found.")
                    continue

            self.get_completion_stream(
                message=text,
                event_handler=TermEventHandler,
                recipient_agent=recipient_agent,
            )

    def get_customgpt_schema(self, url: str):
        """Returns the OpenAPI schema for the agency from the CEO agent, that you can use to integrate with custom gpts.

        Parameters:
            url (str): Your server url where the api will be hosted.
        """

        return self.ceo.get_openapi_schema(url)

    def plot_agency_chart(self):
        pass

    def _init_agents(self):
        """
        Initializes all agents in the agency with unique IDs, shared instructions, and OpenAI models.

        This method iterates through each agent in the agency, assigns a unique ID, adds shared instructions, and initializes the OpenAI models for each agent.

        There are no input parameters.

        There are no output parameters as this method is used for internal initialization purposes within the Agency class.
        """
        if self.settings_callbacks:
            loaded_settings = self.settings_callbacks["load"]()
            with open(self.settings_path, "w") as f:
                json.dump(loaded_settings, f, indent=4)

        for agent in self.agents:
            assert isinstance(agent, Agent)
            print(f"Initializing agent... {agent.name}")
            if "temp_id" in agent.id:
                agent.id = None

            agent.agency = self
            agent.add_shared_instructions(self.shared_instructions)
            agent.settings_path = self.settings_path

            if self.shared_files:
                if isinstance(self.shared_files, str):
                    self.shared_files = [self.shared_files]

                if isinstance(agent.files_folder, str):
                    agent.files_folder = [agent.files_folder]
                    agent.files_folder += self.shared_files
                elif isinstance(agent.files_folder, list):
                    agent.files_folder += self.shared_files

            if self.temperature is not None and agent.temperature is None:
                agent.temperature = self.temperature
            if self.top_p and agent.top_p is None:
                agent.top_p = self.top_p
            if self.max_prompt_tokens is not None and agent.max_prompt_tokens is None:
                agent.max_prompt_tokens = self.max_prompt_tokens
            if (
                self.max_completion_tokens is not None
                and agent.max_completion_tokens is None
            ):
                agent.max_completion_tokens = self.max_completion_tokens
            if (
                self.truncation_strategy is not None
                and agent.truncation_strategy is None
            ):
                agent.truncation_strategy = self.truncation_strategy

            if not agent.shared_state:
                agent.shared_state = self.shared_state

            agent.init_oai()

        if self.settings_callbacks:
            with open(self.agents[0].get_settings_path(), "r") as f:
                settings = f.read()
            settings = json.loads(settings)
            self.settings_callbacks["save"](settings)

    def _init_threads(self):
        """
        Initializes threads for communication between agents within the agency.

        This method creates Thread objects for each pair of interacting agents as defined in the agents_and_threads attribute of the Agency. Each thread facilitates communication and task execution between an agent and its designated recipient agent.

        No input parameters.

        Output Parameters:
            This method does not return any value but updates the agents_and_threads attribute with initialized Thread objects.
        """
        self.main_thread = Thread(self.user, self.ceo)

        # load thread ids
        loaded_thread_ids = {}
        if self.threads_callbacks:
            loaded_thread_ids = self.threads_callbacks["load"]()
            if "main_thread" in loaded_thread_ids and loaded_thread_ids["main_thread"]:
                self.main_thread.id = loaded_thread_ids["main_thread"]
            else:
                self.main_thread.init_thread()

        # Save main_thread into agents_and_threads
        self.agents_and_threads["main_thread"] = self.main_thread

        # initialize threads
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            for other_agent, items in threads.items():
                # create thread class
                self.agents_and_threads[agent_name][other_agent] = self._thread_type(
                    self._get_agent_by_name(items["agent"]),
                    self._get_agent_by_name(items["recipient_agent"]),
                )

                # load thread id if available
                if (
                    agent_name in loaded_thread_ids
                    and other_agent in loaded_thread_ids[agent_name]
                ):
                    self.agents_and_threads[agent_name][
                        other_agent
                    ].id = loaded_thread_ids[agent_name][other_agent]
                # init threads if threre are threads callbacks so the ids are saved for later use
                elif self.threads_callbacks:
                    self.agents_and_threads[agent_name][other_agent].init_thread()

        # save thread ids
        if self.threads_callbacks:
            loaded_thread_ids = {}
            for agent_name, threads in self.agents_and_threads.items():
                if agent_name == "main_thread":
                    continue
                loaded_thread_ids[agent_name] = {}
                for other_agent, thread in threads.items():
                    loaded_thread_ids[agent_name][other_agent] = thread.id

            loaded_thread_ids["main_thread"] = self.main_thread.id

            self.threads_callbacks["save"](loaded_thread_ids)

    def _parse_agency_chart(self, agency_chart):
        """
        Parses the provided agency chart to initialize and organize agents within the agency.

        Parameters:
            agency_chart: A structure representing the hierarchical organization of agents within the agency.
                    It can contain Agent objects and lists of Agent objects.

        This method iterates through each node in the agency chart. If a node is an Agent, it is set as the CEO if not already assigned.
        If a node is a list, it iterates through the agents in the list, adding them to the agency and establishing communication
        threads between them. It raises an exception if the agency chart is invalid or if multiple CEOs are defined.
        """
        if not isinstance(agency_chart, list):
            raise Exception("Invalid agency chart.")

        if len(agency_chart) == 0:
            raise Exception("Agency chart cannot be empty.")

        for node in agency_chart:
            if isinstance(node, Agent):
                if not self.ceo:
                    self.ceo = node
                    self._add_agent(self.ceo)
                else:
                    self._add_agent(node)
                self._add_main_recipient(node)

            elif isinstance(node, list):
                for i, agent in enumerate(node):
                    print(f"checking {agent.name}...")
                    if not isinstance(agent, Agent):
                        raise Exception("Invalid agency chart.")

                    index = self._add_agent(agent)

                    if i == len(node) - 1:
                        continue

                    if agent.name not in self.agents_and_threads.keys():
                        self.agents_and_threads[agent.name] = {}

                    if i < len(node) - 1:
                        other_agent = node[i + 1]
                        if other_agent.name == agent.name:
                            continue
                        if (
                            other_agent.name
                            not in self.agents_and_threads[agent.name].keys()
                        ):
                            self.agents_and_threads[agent.name][other_agent.name] = {
                                "agent": agent.name,
                                "recipient_agent": other_agent.name,
                            }
            else:
                raise Exception("Invalid agency chart.")

    def _add_agent(self, agent):
        """
        Adds an agent to the agency, assigning a temporary ID if necessary.

        Parameters:
            agent (Agent): The agent to be added to the agency.

        Returns:
            int: The index of the added agent within the agency's agents list.

        This method adds an agent to the agency's list of agents. If the agent does not have an ID, it assigns a temporary unique ID. It checks for uniqueness of the agent's name before addition. The method returns the index of the agent in the agency's agents list, which is used for referencing the agent within the agency.
        """
        if not agent.id:
            # assign temp id
            agent.id = "temp_id_" + str(uuid.uuid4())
        if agent.id not in self._get_agent_ids():
            if agent.name in self._get_agent_names():
                raise Exception("Agent names must be unique.")
            self.agents.append(agent)
            return len(self.agents) - 1
        else:
            return self._get_agent_ids().index(agent.id)

    def _add_main_recipient(self, agent):
        """
        Adds an agent to the agency's list of main recipients.

        Parameters:
            agent (Agent): The agent to be added to the agency's list of main recipients.

        This method adds an agent to the agency's list of main recipients. These are agents that can be directly contacted by the user.
        """
        main_recipient_ids = [agent.id for agent in self.main_recipients]

        if agent.id not in main_recipient_ids:
            self.main_recipients.append(agent)

    def _read_instructions(self, path):
        """
        Reads shared instructions from a specified file and stores them in the agency.

        Parameters:
            path (str): The file path from which to read the shared instructions.

        This method opens the file located at the given path, reads its contents, and stores these contents in the 'shared_instructions' attribute of the agency. This is used to provide common guidelines or instructions to all agents within the agency.
        """
        path = path
        with open(path, "r") as f:
            self.shared_instructions = f.read()

    def _create_special_tools(self):
        """
        Creates and assigns 'SendMessage' tools to each agent based on the agency's structure.

        This method iterates through the agents and threads in the agency, creating SendMessage tools for each agent. These tools enable agents to send messages to other agents as defined in the agency's structure. The SendMessage tools are tailored to the specific recipient agents that each agent can communicate with.

        No input parameters.

        No output parameters; this method modifies the agents' toolset internally.
        """
        for agent_name, threads in self.agents_and_threads.items():
            if agent_name == "main_thread":
                continue
            recipient_names = list(threads.keys())
            recipient_agents = self._get_agents_by_names(recipient_names)
            if len(recipient_agents) == 0:
                continue
            agent = self._get_agent_by_name(agent_name)
            agent.add_tool(self._create_send_message_tool(agent, recipient_agents))
            if self._thread_type == ThreadAsync:
                agent.add_tool(self._create_get_response_tool(agent, recipient_agents))

    def _create_send_message_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a SendMessage tool to enable an agent to send messages to specified recipient agents.


        Parameters:
            agent (Agent): The agent who will be sending messages.
            recipient_agents (List[Agent]): A list of recipient agents who can receive messages.

        Returns:
            SendMessage: A SendMessage tool class that is dynamically created and configured for the given agent and its recipient agents. This tool allows the agent to send messages to the specified recipients, facilitating inter-agent communication within the agency.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        agent_descriptions = ""
        for recipient_agent in recipient_agents:
            if not recipient_agent.description:
                continue
            agent_descriptions += recipient_agent.name + ": "
            agent_descriptions += recipient_agent.description + "\n"

        class SendMessage(self.send_message_tool_class):
            recipient: recipients = Field(..., description=agent_descriptions)

            @field_validator("recipient")
            @classmethod
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(
                        f"Recipient {value} is not valid. Valid recipients are: {recipient_names}"
                    )
                return value

        SendMessage._caller_agent = agent
        SendMessage._agents_and_threads = self.agents_and_threads

        return SendMessage

    def _create_get_response_tool(self, agent: Agent, recipient_agents: List[Agent]):
        """
        Creates a CheckStatus tool to enable an agent to check the status of a task with a specified recipient agent.
        """
        recipient_names = [agent.name for agent in recipient_agents]
        recipients = Enum("recipient", {name: name for name in recipient_names})

        outer_self = self

        class GetResponse(BaseTool):
            """This tool allows you to check the status of a task or get a response from a specified recipient agent, if the task has been completed. You must always use 'SendMessage' tool with the designated agent first."""

            recipient: recipients = Field(
                ...,
                description=f"Recipient agent that you want to check the status of. Valid recipients are: {recipient_names}",
            )

            @field_validator("recipient")
            def check_recipient(cls, value):
                if value.value not in recipient_names:
                    raise ValueError(
                        f"Recipient {value} is not valid. Valid recipients are: {recipient_names}"
                    )
                return value

            def run(self):
                thread = outer_self.agents_and_threads[self._caller_agent.name][
                    self.recipient.value
                ]

                return thread.check_status()

        GetResponse._caller_agent = agent

        return GetResponse

    def _get_agent_by_name(self, agent_name):
        """
        Retrieves an agent from the agency based on the agent's name.

        Parameters:
            agent_name (str): The name of the agent to be retrieved.

        Returns:
            Agent: The agent object with the specified name.

        Raises:
            Exception: If no agent with the given name is found in the agency.
        """
        for agent in self.agents:
            if agent.name == agent_name:
                return agent
        raise Exception(f"Agent {agent_name} not found.")

    def _get_agents_by_names(self, agent_names):
        """
        Retrieves a list of agent objects based on their names.

        Parameters:
            agent_names: A list of strings representing the names of the agents to be retrieved.

        Returns:
            A list of Agent objects corresponding to the given names.
        """
        return [self._get_agent_by_name(agent_name) for agent_name in agent_names]

    def _get_agent_ids(self):
        """
        Retrieves the IDs of all agents currently in the agency.

        Returns:
            List[str]: A list containing the unique IDs of all agents.
        """
        return [agent.id for agent in self.agents]

    def _get_agent_names(self):
        """
        Retrieves the names of all agents in the agency.

        Returns:
            List[str]: A list of names of all agents currently part of the agency.
        """
        return [agent.name for agent in self.agents]

    def _get_class_folder_path(self):
        """
        Retrieves the absolute path of the directory containing the class file.

        Returns:
            str: The absolute path of the directory where the class file is located.
        """
        return os.path.abspath(os.path.dirname(inspect.getfile(self.__class__)))

    def delete(self):
        """
        This method deletes the agency and all its agents, cleaning up any files and vector stores associated with each agent.
        """
        for agent in self.agents:
            agent.delete()

    def _init_file(self, file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                pass
        except Exception as e:
            print(f"Creating {file_path}...")

    def _init_dir(self, dir_path):
        import shutil

        try:
            shutil.rmtree(dir_path)
        except:
            pass
        os.mkdir(dir_path)

    def _rm_file(self, file_path):
        if os.path.exists(file_path):
            os.remove(file_path)

    files_path = os.path.join("agents", "files")
    # 未使用的文件路径
    request_path = os.path.join(files_path, "completed_requests.json")
    completed_step_path = os.path.join(files_path, "completed_steps.json")
    completed_subtask_path = os.path.join(files_path, "completed_sub_tasks.json")
    completed_task_path = os.path.join(files_path, "completed_tasks.json")
    context_index_path = os.path.join(files_path, "context_index.json")
    context_path = os.path.join(files_path, "context.json")
    # 使用的文件路径
    error_path = os.path.join(files_path, "error.json")
    text_path = os.path.join(files_path, "text.txt")
    CONTEXT_TREE_PATH = os.path.join(files_path, "context_tree.json")
    contexts_path = os.path.join(files_path, "api_results")

    def init_files(self):
        # self._init_dir(self.files_path)
        # self._init_dir(self.contexts_path)
        self._init_file(self.error_path)
        # self._init_file(self.completed_step_path)
        # self._init_file(self.completed_subtask_path)
        # self._init_file(self.completed_task_path)
        # self._init_file(self.context_index_path)
        self._rm_file(self.request_path)
        self._rm_file(self.completed_step_path)
        self._rm_file(self.completed_subtask_path)
        self._rm_file(self.completed_task_path)
        self._rm_file(self.context_index_path)
        self._rm_file(self.context_path)

    def create_cap_group_agent_threads(
        self, cap_group_agents: Dict[str, List]
    ) -> Dict[str, List[Thread]]:
        capgroup_thread = {}
        for key in cap_group_agents.keys():
            capgroup_thread[key] = []
            for agent in cap_group_agents[key]:
                capgroup_thread[key].append(Thread(self.user, agent))
        return capgroup_thread

    def create_cap_agent_thread(
        self, cap_group: str, cap_agents: Dict[str, List]
    ) -> Dict[str, Thread]:
        cap_agent_thread = {}
        for agent in cap_agents[cap_group]:
            cap_agent_thread[agent.name] = Thread(self.user, agent)
        return cap_agent_thread

    def test_single_cap_agent(
        self,
        step: dict,
        cap_group: str,
        plan_agents: Dict[str, Agent],
        cap_group_agents: Dict[str, List],
        cap_agents: Dict[str, List],
    ):
        """
        用户请求 -> 事务*n1 -> 子任务*n2 -> 步骤*n3
        事务是不可分割（指完成过程中）的任务，如安装软件等，必须完成之后才能进行其他操作；
        子任务是对事务进行拆分，按照能力群拆分，类似于流水线；
        步骤对应能力，指具体操作步骤，和能力Agent关联
        """
        self._setup_autocomplete()  # Prepare readline for autocomplete

        self.init_files()

        print("Initialization Successful.\n")

        cap_agent_threads = {}
        for key in cap_agents:
            cap_agent_threads[key] = self.create_cap_agent_thread(
                cap_group=key, cap_agents=cap_agents
            )

        # task_id = 0
        result, new_context = self.capability_agents_processor(
            step=step, cap_group=cap_group, cap_agent_threads=cap_agent_threads
        )

    def execute_task(executors, task):
        # 执行任务，具体细节需要实现
        task_str = json.dumps(task, ensure_ascii=False, indent=2)
        # ...
        return {}

    def hypothesize_test(
            self,
            user_request,
            ideator,
            task_planner,
            executors,
            verifier
    ):
        task_planner_thread = Thread(self.user, task_planner)
        ideator_thread = Thread(self.user, ideator)
        verifier_thread = Thread(self.user, verifier)
        executor_threads = []
        for executor in executors:
            executor_threads.append(Thread(self.user, executor))
        text = user_request
        # 1. 获取假设
        hypo = self.json_get_completion(ideator_thread, text)
        subtask_str = self.json_get_completion(task_planner_thread, hypo)
        subtask = json.loads(subtask_str)
        result = []
        for task in subtask:
            res = self.execute_task(executors, task)
            result.append(res)
        message = {
            "hypothesis": hypo,
            "result": result
        }
        ver = self.json_get_completion(verifier_thread, json.dumps(message, ensure_ascii=False, indent=2))
        return ver
    
    def correlation_test(
        self,
        user_request,
        experts # {name: agent}
    ):
        expert_threads = {}
        description = {}
        for name, expert in experts.items():
            expert_threads[name] = Thread(self.user, expert)
            description[name] = expert.instructions
        # 输入包括所有expert的介绍；用户需求；已经获取的信息
        # 输出结果: {"expert": 找哪个expert补充信息; "question": 具体问的问题;}
        
        message = {
            "description": description,
            "user_request": user_request,
        }

        information = {}
        while True:
            count = 0
            for name in experts.keys():
                if name not in information:
                    information[name] = []
                ques = message | {"information": information[name]}
                res_str = self.json_get_completion(expert_threads[name], json.dumps(ques, ensure_ascii=False, indent=2))
                res = json.loads(res_str)
                if "expert" in res:
                    ask_expert = res["expert"]
                    question = res["question"]
                    info = self.json_get_completion(expert_threads[ask_expert], question)
                    information[name].append(info)
                else:
                    count += 1
            if count == len(experts):
                break

    def consensus_test(
        self,
        user_request,
        coordinator, 
        debators
    ):
        # coordinators保证讨论轨迹
        # coordinators返回judge: {result: debate是否合理, explanation: 解释}
        # debator返回debate: {option: 认可度, explanation: 对option的解释, }
        coordinator_thread = Thread(self.user, coordinator)
        debator_threads = []
        n = len(debators)
        for debator in debators:
            debator_threads.append(Thread(self.user, debator))
        debate_info = {
            "user_request": user_request
        }
        # 输入：用户请求，上一位辩论者的观点和解释
        debate = {}
        while True:
            count = 0
            for debator_thread in debator_threads:
                if debate:
                    debate_info["option"] = debate["option"]
                    debate_info["explanation"] = debate["explanation"]
                review = ""
                while True:
                    debate_input = debate_info
                    if review:
                        debate_input["review"] = review
                    debate_str = self.json_get_completion(debator_thread, json.dumps(debate_input, ensure_ascii=False, indent=2))
                    judge_str = self.json_get_completion(coordinator_thread, debate_str)
                    judge = json.loads(judge_str)
                    if judge["result"].lower() == 'yes':
                        debate = json.loads(debate_str)
                        break
                    review = judge["explanation"]
                count += debate["option"]
            # 每轮之后计算认可度总和
            if count >= 0.5*n:
                return True
            if count <= -0.5*n:
                return False
            
    def task_planning(
        self,
        original_request: str,
        plan_agents: Dict[str, Agent],
        cap_group_agents: Dict[str, List],
        cap_agents: Dict[str, List],
        request_id: str,
    ):
        """
        用户请求 -> 事务*n1 -> 子任务*n2 -> 步骤*n3
        事务是不可分割（指完成过程中）的任务，如安装软件等，必须完成之后才能进行其他操作；
        子任务是对事务进行拆分，按照能力群拆分，类似于流水线；
        步骤对应能力，指具体操作步骤，和能力Agent关联
        """
        # 设置命令行补全功能
        self._setup_autocomplete()  # Prepare readline for autocomplete
        # 初始化流程相关的文件和目录
        self.init_files()

        print("Initialization Successful.\n")

        # 初始化任务树
        self.init_context_tree(request_id=request_id, content=original_request)

        # 判断是否启用“代码级调度”模式（通过环境变量 DEBUG_CODE_SCHEDULING 控制）
        code_scheduling = os.getenv("DEBUG_CODE_SCHEDULING")
        if code_scheduling is None or code_scheduling.lower() != "true":
            code_scheduling = False
        else:
            code_scheduling = True

        # 取出各类规划/检查/调度的智能体（Agent）
        task_planner = plan_agents["task_planner"]
        task_inspector = plan_agents["task_inspector"]
        subtask_planner = plan_agents["subtask_planner"]
        subtask_inspector = plan_agents["subtask_inspector"]
        step_inspector = plan_agents["step_inspector"]
        # 创建用户与各智能体的对话线程（Thread）
        task_planner_thread = Thread(self.user, task_planner)
        task_inspector_thread = Thread(self.user, task_inspector)
        subtask_planner_thread = Thread(self.user, subtask_planner)
        subtask_inspector_thread = Thread(self.user, subtask_inspector)
        step_inspector_thread = Thread(self.user, step_inspector)

        # 如果未开启代码级调度，还需要分别为task和subtask调度器创建线程
        if not code_scheduling:
            task_scheduler = plan_agents["task_scheduler"]
            subtask_scheduler = plan_agents["subtask_scheduler"]
            task_scheduler_thread = Thread(self.user, task_scheduler)
            subtask_scheduler_thread = Thread(self.user, subtask_scheduler)

        # 为每个能力群的智能体批量创建线程
        cap_group_thread = self.create_cap_group_agent_threads(
            cap_group_agents=cap_group_agents
        )
        # cap_group_thread[能力群名称] = [该能力群的planner的Thread, 该能力群的scheduler的Thread]

        # 为每个能力群下的每个能力agent创建线程
        cap_agent_threads = {}
        for key in cap_agents:
            cap_agent_threads[key] = self.create_cap_agent_thread(
                cap_group=key, cap_agents=cap_agents
            )
        # cap_agent_threads[能力群名称][能力agent名称] = 该能力agent的Thread

        original_request_error_flag = False
        original_request_error_message = ""
        error_id = 0

        # 主循环：规划用户原始请求，拆解为task流程图
        while True:
            # task_id = task_id + 1

            # 1. 任务规划层，生成task级流程图和调度所需信息
            task_graph, tasks_need_scheduled, _ = self.planning_layer(
                message=original_request,
                original_request=original_request,
                planner_thread=task_planner_thread,
                error_message=original_request_error_message,
                inspector_thread=task_inspector_thread,
                node_color="lightblue",
                overall_id="original request",
            )

            # 重置错误标志，清理错误文件
            original_request_error_flag = False
            self._init_file(self.error_path)

            # id2task 用于记录task_id到task对象的映射
            id2task = {}
            task_graph_json = json.loads(task_graph)
            for key in task_graph_json.keys():
                task = task_graph_json[key]
                id2task[task["id"]] = task
                self.update_context_tree(
                    request_id=request_id,
                    task_id=task["id"],
                    status="pending",
                    title=task["title"],
                    description=task["description"],
                )
            completed_task_ids = []

            # 任务调度循环
            while True:
                # 2. 任务调度层，确定当前可执行的task列表
                if code_scheduling:
                    next_task_list = self.code_scheduling_layer(
                        overall_id="original request",
                        graph=task_graph_json,
                        completed_ids=completed_task_ids,
                    )
                else:
                    tasks_scheduled = self.scheduling_layer(
                        scheduler_thread=task_scheduler_thread,
                        message=tasks_need_scheduled,
                    )
                    tasks_scheduled_json = json.loads(tasks_scheduled)
                    next_task_list = tasks_scheduled_json["next_tasks"]

                # 没有可执行task则说明全部完成，退出循环
                if not next_task_list:
                    break

                # 逐个执行可调度的task
                for next_task_id in next_task_list:
                    # 规划并执行单个task，不可中途终止。如果出现错误则重新规划task。
                    task_error_flag = False
                    task_error_message = ""

                    next_task = id2task[next_task_id]

                    # 传递给subtask规划的信息
                    subtask_input = {
                        "title": next_task['title'],
                        "description": next_task['description'],
                    }
                        # "total_task_graph": task_graph_json,
                    
                    self.update_context_tree(
                        request_id = request_id,
                        task_id = next_task_id,
                        status = "executing",
                        title = next_task['title'],
                        description = next_task['description']
                    )

                    console.rule()
                    print(
                        f"completed tasks: {(', '.join([str(id)+' ('+task_graph_json[id]['title']+')' for id in completed_task_ids])) if completed_task_ids else 'none'}"
                    )
                    print(f"next task -> {next_task_id} ({next_task['title']})")

                    # task内循环：不断尝试把task拆分为subtask（能力群相关）
                    while True:
                        # 3. 子任务规划层，生成subtask级流程图和调度所需信息
                        subtask_graph, subtasks_need_scheduled, _ = self.planning_layer(
                            message=json.dumps(subtask_input, ensure_ascii=False),
                            original_request=next_task["description"],
                            planner_thread=subtask_planner_thread,
                            error_message=task_error_message,
                            inspector_thread=subtask_inspector_thread,
                            node_color="lightgreen",
                            overall_id=next_task_id,
                        )
                        task_error_flag = False

                        id2subtask = {}
                        subtask_graph_json = json.loads(subtask_graph)
                        for key in subtask_graph_json.keys():
                            subtask = subtask_graph_json[key]
                            id2subtask[subtask["id"]] = subtask
                            self.update_context_tree(
                                request_id=request_id,
                                task_id=next_task_id,
                                subtask_id=subtask["id"],
                                status="pending",
                                title=subtask["title"],
                                description=subtask["description"],
                            )
                        completed_subtask_ids = []

                        # 子任务调度循环
                        while True:
                            # 4. 子任务调度层，确定可执行的subtask列表
                            if code_scheduling:
                                next_subtask_list = self.code_scheduling_layer(
                                    overall_id=next_task_id,
                                    graph=subtask_graph_json,
                                    completed_ids=completed_subtask_ids,
                                )
                            else:
                                subtasks_scheduled = self.scheduling_layer(
                                    scheduler_thread=subtask_scheduler_thread,
                                    message=subtasks_need_scheduled,
                                )
                                subtasks_scheduled_json = json.loads(subtasks_scheduled)
                                next_subtask_list = subtasks_scheduled_json[
                                    "next_subtasks"
                                ]

                            if (
                                not next_subtask_list
                            ):  # 没有可执行subtask则说明全部完成，退出循环
                                break

                            for next_subtask_id in next_subtask_list:
                                # 规划并执行单个subtask，如出错重新规划task。
                                subtask_error_flag = False
                                subtask_error_message = ""

                                next_subtask = id2subtask[next_subtask_id]
                                steps_input = {
                                    "title": next_subtask['title'],
                                    "description": next_subtask['description'],
                                }
                                    # "total_subtask_graph": subtask_graph_json,
                                
                                self.update_context_tree (
                                    request_id = request_id,
                                    task_id = next_task_id,
                                    subtask_id = next_subtask_id,
                                    status = "executing",
                                    title = next_subtask['title'], 
                                    description = next_subtask['description']
                                )

                                console.rule()
                                print(
                                    f"completed tasks: {(', '.join([str(id)+' ('+task_graph_json[id]['title']+')' for id in completed_task_ids])) if completed_task_ids else 'none'}"
                                )
                                print(
                                    f"this task -> {next_task_id} ({next_task['title']})"
                                )
                                print(
                                    f"├ completed subtasks: {(', '.join([str(id)+' ('+subtask_graph_json[id]['title']+')' for id in completed_subtask_ids])) if completed_subtask_ids else 'none'}"
                                )
                                print(
                                    f"└ next subtask -> {next_subtask_id} ({next_subtask['title']})"
                                )
                                next_subtask_cap_group = next_subtask[
                                    "capability_group"
                                ]

                                while True:
                                    # 5. 步骤规划层，生成step级流程图和调度所需信息
                                    steps_graph, steps_need_scheduled, _ = (
                                        self.planning_layer(
                                            message=json.dumps(
                                                steps_input, ensure_ascii=False
                                            ),
                                            original_request=next_subtask[
                                                "description"
                                            ],
                                            planner_thread=cap_group_thread[
                                                next_subtask_cap_group
                                            ][0],
                                            error_message=subtask_error_message,
                                            inspector_thread=step_inspector_thread,
                                            node_color="white",
                                            overall_id=next_subtask_id,
                                        )
                                    )
                                    subtask_error_flag = False
                                    # id2step 用于记录step_id到step对象的映射
                                    id2step = {}
                                    steps_graph_json = json.loads(steps_graph)
                                    for key in steps_graph_json.keys():
                                        step = steps_graph_json[key]
                                        id2step[step["id"]] = step
                                        self.update_context_tree(
                                            request_id=request_id,
                                            task_id=next_task_id,
                                            subtask_id=next_subtask_id,
                                            step_id=step["id"],
                                            status="pending",
                                            title=step["title"],
                                            description=step["description"],
                                        )
                                    completed_step_ids = []

                                    # 步骤调度循环
                                    while True:
                                        if code_scheduling:
                                            next_step_list = self.code_scheduling_layer(
                                                overall_id=next_subtask_id,
                                                graph=steps_graph_json,
                                                completed_ids=completed_step_ids,
                                            )
                                        else:
                                            steps_scheduled = self.scheduling_layer(
                                                scheduler_thread=cap_group_thread[
                                                    next_subtask_cap_group
                                                ][1],
                                                message=steps_need_scheduled,
                                            )
                                            steps_scheduled_json = json.loads(
                                                steps_scheduled
                                            )
                                            next_step_list = steps_scheduled_json[
                                                "next_steps"
                                            ]
                                        # 没有可执行step则说明全部完成，退出循环
                                        if not next_step_list:
                                            break
                                        # 执行单个step，如出错重新规划task。
                                        for next_step_id in next_step_list:
                                            # 单个step的错误标志和信息
                                            step_error_flag = False
                                            step_error_message = ""

                                            next_step = id2step[next_step_id]

                                            self.update_context_tree(
                                                request_id = request_id,
                                                task_id = next_task_id,
                                                subtask_id = next_subtask_id,
                                                step_id = next_step_id,
                                                status = "executing",
                                                title = next_step['title'],
                                                description = next_step['description']
                                            )

                                            console.rule()
                                            print(
                                                f"completed tasks: {(', '.join([str(id)+' ('+task_graph_json[id]['title']+')' for id in completed_task_ids])) if completed_task_ids else 'none'}"
                                            )
                                            print(
                                                f"this task -> {next_task_id} ({next_task['title']})"
                                            )
                                            print(
                                                f"├ completed subtasks: {(', '.join([str(id)+' ('+subtask_graph_json[id]['title']+')' for id in completed_subtask_ids])) if completed_subtask_ids else 'none'}"
                                            )
                                            print(
                                                f"└ this subtask -> {next_subtask_id} ({next_subtask['title']})"
                                            )
                                            print(
                                                f"  ├ completed steps: {(', '.join([str(id)+' ('+steps_graph_json[id]['title']+')' for id in completed_step_ids])) if completed_step_ids else 'none'}"
                                            )
                                            print(
                                                f"  └ next step -> {next_step_id} ({next_step['title']})"
                                            )

                                            while True:
                                                try:
                                                    # 7. 能力agent执行单个step
                                                    action = self.capability_agents_processor(step=next_step, cap_group=next_subtask_cap_group, cap_agent_threads=cap_agent_threads)
                                                    result = action.get('result', "FAIL")
                                                    context = action.get('context', "No context provided.")
                                                    assert result == 'SUCCESS' or result == 'FAIL', f"Unknown result: {result}" 
                                                    
                                                    self.update_context_tree(
                                                        request_id = request_id,
                                                        task_id = next_task_id,
                                                        subtask_id = next_subtask_id,
                                                        step_id = next_step_id,
                                                        action = action,
                                                    )

                                                    if result == "SUCCESS":
                                                        pass
                                                    elif result == "FAIL":
                                                        # 如果失败，记录并更新error
                                                        error_id = error_id + 1
                                                        step_error_flag = True
                                                        step_error_message = context

                                                        self.update_error(error_id = error_id, error = action, step = next_step)

                                                except Exception as e:
                                                    # 更新error
                                                    error_id = error_id + 1
                                                    step_error_flag = True
                                                    step_error_message = str(e)

                                                # 如果没有错误则退出该step循环，否则进入下一级错误处理
                                                if not step_error_flag:
                                                    console.rule()
                                                    print(
                                                        f"    {next_step_id} ({next_step['title']}) complete"
                                                    )
                                                    break
                                                else:
                                                    console.rule()
                                                    print(
                                                        f"    {next_step_id} ({next_step['title']}) failed, error: {step_error_message}"
                                                    )

                                                    self.clear_context_tree_node(
                                                        request_id=request_id,
                                                        task_id=next_task_id,
                                                        subtask_id=next_subtask_id,
                                                        step_id=next_step_id,
                                                    )

                                                    # continue # 重新执行step
                                                    subtask_error_flag = True
                                                    subtask_error_message = (
                                                        step_error_message
                                                    )
                                                    break  # 失败则跳出，重新规划subtask

                                            if subtask_error_flag:
                                                break
                                            # 本次step完成，加入已完成列表
                                            completed_step_ids.append(next_step_id)

                                            self.update_context_tree(
                                                request_id=request_id,
                                                task_id=next_task_id,
                                                subtask_id=next_subtask_id,
                                                step_id=next_step_id,
                                                status="completed",
                                            )

                                        if subtask_error_flag:
                                            break
                                        # 本次step调度结束

                                    # 本subtask的所有step结束
                                    if not subtask_error_flag:
                                        # 如果step全都正常完成，更新已完成subtask
                                        console.rule()
                                        print(
                                            f"  {next_subtask_id} ({next_subtask['title']}) complete"
                                        )
                                        break
                                    else:
                                        console.rule()
                                        print(
                                            f"  {next_subtask_id} ({next_subtask['title']}) failed, error: {subtask_error_message}"
                                        )

                                        self.clear_context_tree_node(
                                            request_id=request_id,
                                            task_id=next_task_id,
                                            subtask_id=next_subtask_id,
                                        )

                                        # continue # 重新规划subtask
                                        task_error_flag = True
                                        task_error_message = subtask_error_message
                                        break  # 失败则跳出，重新规划task

                                if task_error_flag:
                                    break
                                # 本次subtask完成，加入已完成列表
                                completed_subtask_ids.append(next_subtask_id)

                                self.update_context_tree(
                                    request_id=request_id,
                                    task_id=next_task_id,
                                    subtask_id=next_subtask_id,
                                    status="completed",
                                )

                            if task_error_flag:
                                break
                            # 本次subtask调度结束

                        # 本次task的所有subtask结束
                        if not task_error_flag:
                            # 如果subtask全都正常完成，更新已完成task
                            console.rule()
                            print(f"{next_task_id} ({next_task['title']}) complete")
                            break
                        else:
                            console.rule()
                            print(
                                f"{next_task_id} ({next_task['title']}) failed, error: {task_error_message}"
                            )

                            self.clear_context_tree_node(
                                request_id=request_id, task_id=next_task_id
                            )
                            continue  # 有错误则重新规划task

                    # 本次task完成，加入已完成列表
                    completed_task_ids.append(next_task_id)

                    self.update_context_tree(
                        request_id=request_id,
                        task_id=next_task_id,
                        status="completed",
                    )

                if original_request_error_flag:
                    break
                # 本次task调度结束

            # 所有task完成
            if not original_request_error_flag:
                console.rule()
                print(f"original request complete")

                self.update_context_tree(
                    request_id=request_id,
                    status="completed",
                )
                break
                # 本用户请求的所有task结束
            else:
                console.rule()
                print(
                    f"original request failed, error: {original_request_error_message}"
                )
                self.clear_context_tree_node(request_id=request_id)
                continue  # 重新规划用户请求

    def task_planning_rag(
        self,
        original_request: str,
        plan_agents: Dict[str, Agent],
        cap_group_agents: Dict[str, List],
        cap_agents: Dict[str, List],
        request_id: str,
    ):
        """
        用户请求 -> 任务*n -> 任务细化层，得到该任务的能力agent列表 -> 执行任务 -> 单个task执行不超过3次失败则根据错误信息调用任务细化层重新细化该task；否则调用任务细化层重新规划用户请求。
        任务是不可分割（指完成过程中）的任务，必须完成之后才能进行其他操作，任务按照能力群拆分。
        任务细化层，根据能力群对task细化或重新规划，和能力Agent关联。
        """
        # 设置命令行补全功能
        self._setup_autocomplete()  # Prepare readline for autocomplete
        # 初始化流程相关的文件和目录
        self.init_files()

        print("Initialization Successful.\n")

        # 初始化任务树
        self.init_context_tree(request_id=request_id, content=original_request)

        # 判断是否启用“代码级调度”模式（通过环境变量 DEBUG_CODE_SCHEDULING 控制）
        code_scheduling = os.getenv("DEBUG_CODE_SCHEDULING")
        if code_scheduling is None or code_scheduling.lower() != "true":
            code_scheduling = False
        else:
            code_scheduling = True

        # 取出各类规划/检查/调度/任务细化的智能体（Agent）
        task_planner_rag = plan_agents["task_planner_rag"]
        task_inspector_rag = plan_agents["task_inspector_rag"]
        # 创建用户与各智能体的对话线程（Thread）
        task_planner_rag_thread = Thread(self.user, task_planner_rag)
        task_inspector_rag_thread = Thread(self.user, task_inspector_rag)

        # 如果未开启代码级调度，还需要为task调度器创建线程
        if not code_scheduling:
            task_scheduler_rag = plan_agents["task_scheduler_rag"]
            task_scheduler_rag_thread = Thread(self.user, task_scheduler_rag)

        # 为每个能力群的细化智能体批量创建线程
        cap_group_thread = self.create_cap_group_agent_threads(
            cap_group_agents=cap_group_agents
        )
        # cap_group_thread[能力群名称] = [该能力群的planner的Thread, 该能力群的scheduler的Thread]

        # 为每个能力群下的每个能力agent创建线程
        cap_agent_threads = {}
        for key in cap_agents:
            cap_agent_threads[key] = self.create_cap_agent_thread(
                cap_group=key, cap_agents=cap_agents
            )
        # cap_agent_threads[能力群名称][能力agent名称] = 该能力agent的Thread

        original_request_error_flag = False
        original_request_error_message = ""
        error_id = 0
        # 用户在与rag agent对话时，除原始用户请求的所有累加输入
        other_input = ""

        # 针对用户输入的循环：不断尝试把输入拆分为task（能力群相关）
        # 记录是第几个rag session
        plan_original_request_num = "0"
        while True:
            # 任务规划层，生成task的（subtask级）流程图和调度所需信息
            task_graph, tasks_need_scheduled, other_input = self.planning_layer(
                message=original_request,
                original_request=original_request,
                planner_thread=task_planner_rag_thread,
                error_message=original_request_error_message,
                inspector_thread=task_inspector_rag_thread,
                node_color="lightblue",
                overall_id="original request",
                plan_num=plan_original_request_num,
                other_input=other_input,
            )

            # 重置错误标志，清理错误文件
            original_request_error_flag = False
            self._init_file(self.error_path)

            id2task = {}
            task_graph_json = json.loads(task_graph)
            for key in task_graph_json.keys():
                task = task_graph_json[key]
                id2task[task["id"]] = task
                self.update_context_tree(
                    request_id=request_id,
                    task_id=task["id"],
                    status="pending",
                    title=task["title"],
                    description=task["description"],
                )
            completed_task_ids = []

            # 任务调度循环
            while True:
                # 任务调度层，确定可执行的task列表（能力相关）
                if code_scheduling:
                    next_task_list = self.code_scheduling_layer(
                        overall_id="original request",
                        graph=task_graph_json,
                        completed_ids=completed_task_ids,
                    )
                else:
                    tasks_scheduled = self.scheduling_layer(
                        scheduler_thread=task_scheduler_rag_thread,
                        message=tasks_need_scheduled,
                    )
                    tasks_scheduled_json = json.loads(tasks_scheduled)
                    next_task_list = tasks_scheduled_json["next_tasks"]

                if not next_task_list:  # 没有可执行task则说明全部完成，退出循环
                    break

                for next_task_id in next_task_list:
                    # 细化并执行单个task
                    task_error_flag = False
                    task_error_message = ""

                    next_task = id2task[next_task_id]
                    task_input = {
                        "title": next_task["title"],
                        "description": next_task["description"],
                        "total_task_graph": task_graph_json,
                        "last_error": "",
                    }

                    self.update_context_tree(
                        request_id=request_id, task_id=next_task_id, status="executing"
                    )

                    console.rule()
                    print(
                        f"completed tasks: {(', '.join([str(id)+' ('+task_graph_json[id]['title']+')' for id in completed_task_ids])) if completed_task_ids else 'none'}"
                    )
                    print(f"this task -> {next_task_id} ({next_task['title']})")
                    next_task_cap_group = next_task["capability_group"]

                    # 任务细化层
                    optimize_res = self.task_optimizing_layer(
                        message=json.dumps(task_input, ensure_ascii=False),
                        original_request=next_task["description"],
                        optimizer_thread=cap_group_thread[next_task_cap_group][0],
                        overall_id=next_task_id,
                    )
                    optimize_res_json = json.loads(optimize_res)
                    next_task["description"] = optimize_res_json["description"]
                    next_task["agent"] = optimize_res_json["agent"]

                    self.update_context_tree(
                        request_id=request_id,
                        task_id=next_task_id,
                        description=next_task["description"],
                        status="executing",
                    )

                    task_error_num = 0
                    while True:
                        try:
                            # 能力agent执行单个task
                            action = self.capability_agents_processor(
                                    step=next_task,
                                    cap_group=next_task_cap_group,
                                    cap_agent_threads=cap_agent_threads,
                                )
                            result = action.get('result', "FAIL")
                            context = action.get('context', "No context provided.")
                            assert (
                                result == "SUCCESS" or result == "FAIL"
                            ), f"Unknown result: {result}"

                            self.update_context_tree(
                                request_id=request_id,
                                task_id=next_task_id,
                                rag_action=action,
                            )

                            if result == "SUCCESS":
                                task_error_flag = False
                                task_error_message = ""
                            elif result == "FAIL":
                                # 如果失败，记录并更新error
                                error_id = error_id + 1
                                task_error_flag = True
                                task_error_message = context
                                self.update_error(
                                    error_id=error_id, error=context, step=next_task
                                )

                        except Exception as e:
                            # 更新error
                            error_id = error_id + 1
                            task_error_flag = True
                            task_error_message = str(e)

                        # 如果没有错误则退出该task，更新已完成task
                        if not task_error_flag:
                            console.rule()
                            print(f"{next_task_id} ({next_task['title']}) complete")
                            break
                        else:
                            console.rule()
                            print(
                                f"{next_task_id} ({next_task['title']}) failed, error: {task_error_message}"
                            )
                            task_error_num += 1

                            self.clear_context_tree_node(
                                request_id=request_id, task_id=next_task_id
                            )

                            if task_error_num < 3:
                                # 单个task执行不超过3次失败则加上错误信息重新细化该task
                                task_input["last_error"] = task_error_message
                                optimize_again = self.task_optimizing_layer(
                                    message=json.dumps(task_input, ensure_ascii=False),
                                    original_request=next_task["description"],
                                    optimizer_thread=cap_group_thread[
                                        next_task_cap_group
                                    ][0],
                                    overall_id=next_task_id,
                                )
                                optimize_again_json = json.loads(optimize_again)
                                next_task["description"] = optimize_again_json[
                                    "description"
                                ]
                                next_task["agent"] = optimize_again_json["agent"]

                                self.update_context_tree(
                                    request_id=request_id,
                                    task_id=next_task_id,
                                    description=next_task["description"],
                                    status="executing",
                                )
                                continue
                            else:
                                original_request_error_flag = True
                                original_request_error_message = task_error_message
                                break  # 单个task超过3次失败则跳出，重新规划用户请求

                    # 本次task完成，加入已完成列表
                    completed_task_ids.append(next_task_id)

                    self.update_context_tree(
                        request_id=request_id,
                        task_id=next_task_id,
                        status="completed",
                    )

                if original_request_error_flag:
                    break
                # 本次task调度结束

            # 所有task完成
            if not original_request_error_flag:
                console.rule()
                print(f"original request complete")

                self.update_context_tree(
                    request_id=request_id,
                    status="completed",
                )
                break
                # 本用户请求的所有task结束
            else:
                console.rule()
                print(
                    f"original request failed, error: {original_request_error_message}"
                )
                plan_original_request_num = str(int(plan_original_request_num) + 1)
                self.clear_context_tree_node(request_id=request_id)
                continue  # 重新规划用户请求

    def update_error(self, error_id: int, error: str, step: dict):
        try:
            with open(self.error_path, "r", encoding="utf-8") as file:
                try:  # 尝试读取 JSON 数据
                    data = json.load(file)
                except json.JSONDecodeError:  # 如果文件为空或格式错误，则创建一个空字典
                    data = {}
        except FileNotFoundError:
            data = {}
        data[error_id] = {
            "error_id": "error_" + str(error_id),
            "step": step,
            "error": error,
        }
        with open(self.error_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def init_context_tree(self, request_id, content):
        """
        初始化任务树，在任务开始时创建根节点
        """
        with open(self.CONTEXT_TREE_PATH, "r", encoding="utf-8") as file:
            try:  # 尝试读取 JSON 数据
                context_tree = json.load(file)
            except json.JSONDecodeError:  # 如果文件为空或格式错误，则创建一个空字典
                context_tree = {}

        # 添加新的用户请求根节点
        context_tree[request_id] = {
            "content": content,
            "status": "executing",
            "tasks": [],
        }

        with open(self.CONTEXT_TREE_PATH, "w", encoding="utf-8") as f:
            json.dump(context_tree, f, indent=4, ensure_ascii=False)

    def update_context_tree(
        self,
        request_id: str,
        task_id: str = None,
        subtask_id: str = None,
        step_id: str = None,
        status: str = None,
        title: str = None,
        description: str = None,
        action: dict = None,
        rag_action: dict = None,
    ):
        """
        更新任务树中的节点（任务/子任务/步骤）的状态
        """
        # 加载当前任务树
        with open(self.CONTEXT_TREE_PATH, "r", encoding="utf-8") as f:
            context_tree = json.load(f)

        # 获取当前任务
        request = context_tree.get(request_id)
        if not request:
            raise Exception(f"Request {request_id} not found in task tree.")

        # 如果是任务状态变化
        if task_id:
            # 查找任务
            task = next(
                (task for task in request["tasks"] if task["id"] == task_id), None
            )
            if task:
                if rag_action:
                    command = rag_action.get("command")
                    if not command:
                        rag_action_entry = {
                            "tool": rag_action["tool"],
                            "result": rag_action["result"],
                            "context": rag_action["context"],
                        }
                    else:
                        rag_action_entry = rag_action
                    task["rag_actions"].append(rag_action_entry)
                else:
                    if subtask_id:
                        # 查找子任务
                        subtask = next((subtask for subtask in task["subtasks"] if subtask["id"] == subtask_id), None)
                        if subtask:
                            if step_id:
                                # 查找步骤
                                step = next((step for step in subtask["steps"] if step["id"] == step_id), None)
                                if step:
                                    # 更新现有步骤
                                    if action:                                       
                                        step["actions"].append(action)
                                    else:
                                        step["status"] = status
                                else:
                                    # 创建新步骤
                                    step = {
                                        "id": step_id,
                                        "status": status,
                                        "title": title,
                                        "description": description,
                                        "actions": []
                                    }
                                    subtask["steps"].append(step)
                            else:
                                # 更新子任务状态
                                subtask["status"] = status
                        else:
                            # 创建新子任务
                            subtask = {
                                "id": subtask_id,
                                "status": status,
                                "title": title,
                                "description": description,
                                "steps": []
                            }
                            task["subtasks"].append(subtask)
                    else:
                        # 更新任务状态，和描述（rag）
                        task["status"] = status
                        task["description"] = (
                            description if description != None else task["description"]
                        )
            else:
                # 创建新任务
                task = {
                    "id": task_id,
                    "status": status,
                    "title": title,
                    "description": description,
                    "subtasks": [],
                    "rag_actions": [],
                }
                request["tasks"].append(task)
        else:
            # 更新整个请求状态
            request["status"] = status

        # 保存更新后的任务树
        with open(self.CONTEXT_TREE_PATH, "w", encoding="utf-8") as f:
            json.dump(context_tree, f, indent=4, ensure_ascii=False)

    def clear_context_tree_node(
        self,
        request_id: str,
        task_id: str = None,
        subtask_id: str = None,
        step_id: str = None,
    ):
        """
        清空任务树中的节点（任务/子任务/步骤）
        """
        # 加载当前任务树
        with open(self.CONTEXT_TREE_PATH, "r", encoding="utf-8") as f:
            context_tree = json.load(f)

        # 获取当前任务
        request = context_tree.get(request_id)
        if not request:
            raise Exception(f"Request {request_id} not found in task tree.")

        if task_id:
            task = next(
                (task for task in request["tasks"] if task["id"] == task_id), None
            )
            if task:
                if subtask_id:
                    subtask = next(
                        (
                            subtask
                            for subtask in task["subtasks"]
                            if subtask["id"] == subtask_id
                        ),
                        None,
                    )
                    if subtask:
                        if step_id:
                            step = next(
                                (
                                    step
                                    for step in subtask["steps"]
                                    if step["id"] == step_id
                                ),
                                None,
                            )
                            # 清空步骤
                            if step:
                                step["actions"] = []
                            else:
                                raise Exception(f"{step_id} not found in {subtask_id}.")
                        else:
                            # 清空子任务
                            subtask["steps"] = []
                    else:
                        raise Exception(f"{subtask_id} not found in {task_id}.")
                else:
                    # 清空任务
                    task["subtasks"] = []
            else:
                raise Exception(f"{task_id} not found in {request_id}.")
        else:
            # 清空整个请求
            request["tasks"] = []

        # 保存更新后的任务树
        with open(self.CONTEXT_TREE_PATH, "w", encoding="utf-8") as f:
            json.dump(context_tree, f, indent=4, ensure_ascii=False)

    def capability_agents_processor(
        self, step: dict, cap_group: str, cap_agent_threads: dict
    ):
        """
        能力agent执行任务，目前只考虑单个能力agent的情况
        """
        cap_agents = step["agent"]  # 获取当前step指定的能力agent列表
        for agent_name in cap_agents:
            console.rule()
            print(f"{agent_name} EXECUTING {step['id']}...\n")
            # 获取该能力群下，指定能力agent的线程对象
            cap_agent_thread = cap_agent_threads[cap_group][agent_name]
            # 以json格式将step内容发给能力agent执行，获取返回结果
            cap_agent_result = self.json_get_completion(
                cap_agent_thread, json.dumps(step, ensure_ascii=False)
            )
            # 解析agent返回的结果（json字符串）
            cap_agent_result_json = json.loads(cap_agent_result)
        # 执行结果result和返回内容context
        result = cap_agent_result_json['result']
        context = cap_agent_result_json['context']

        output_data = {"result": result, "context": context}
        output_str = json.dumps(output_data, indent=4, ensure_ascii=False)
        print(f"THREAD output:\n{output_str}")
        
        return  cap_agent_result_json # 返回结果

    def scheduling_layer(self, message: str, scheduler_thread: Thread):
        console.rule()
        print(f"{scheduler_thread.recipient_agent.name} SCHEDULING...\n")
        # 调用调度器agent线程，获取调度的下一个任务（或子任务、步骤等）
        scheduler_res = self.json_get_completion(scheduler_thread, message)
        print(f"THREAD output:\n{scheduler_res}")
        return scheduler_res

    def code_scheduling_layer(
        self,
        overall_id: str,
        graph: Dict[str, Dict[str, Any]],
        completed_ids: List[str],
    ) -> List[str]:
        """
        基于依赖关系进行代码级调度，返回下一个可执行的节点id列表
        """
        console.rule()
        print(f"SCHEDULING {overall_id}...\n")
        next_ids = []  # 待执行节点
        completed_id_set = set(completed_ids)
        for id_key, info in graph.items():
            if id_key in completed_id_set:
                continue  # 已完成节点直接跳过
            deps = info.get("dep", [])
            # 检查所有依赖的id是否都已完成
            all_deps_met = all(dep_id in completed_id_set for dep_id in deps)
            if all_deps_met:
                next_ids.append(id_key)  # 依赖全部满足，加入待执行列表
        print(
            f"completed: {(', '.join([str(id)+' ('+graph[id]['title']+')' for id in completed_ids])) if completed_ids else 'none'}"
        )
        print(
            f"scheduled: {(', '.join([str(id)+' ('+graph[id]['title']+')' for id in next_ids])) if next_ids else 'none'}"
        )
        pending_ids = []
        for id_key in graph.keys():
            if id_key not in completed_id_set and id_key not in next_ids:
                pending_ids.append(id_key)
        print(
            f"pending: {(', '.join([str(id)+' ('+graph[id]['title']+')' for id in pending_ids])) if pending_ids else 'none'}"
        )
        return next_ids  # 返回下一个可执行节点的id列表

    def rag_flow(self, original_request: str, plan_num: str):
        load_dotenv()
        ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
        assistant_name = os.getenv("ASSISTANT_NAME")
        session_name = os.getenv("SESSION_NAME")

        rag_object = RAGFlow(api_key=ragflow_api_key, base_url="http://localhost:9222")
        assistant = rag_object.list_chats(name=assistant_name)[0]
        output_format = """
            {
                "is_complete": "0"/"1"（注意带双引号）,
                "response": 提问内容或最终回答（格式为字符串，注意换行时应写换行符不要直接换行）
            }
            """
        instruction = """
            你是一个鲲鹏服务器的运维专家，你只能根据知识库的内容来总结并回答问题，请确保你输出的所有内容都来自于知识库。当所有知识库内容都与问题无关时，你的回答必须包括“知识库中未找到您要的答案！”这句话。
            以下是知识库:
            {knowledge}
            以上是知识库。

            你的输出为以下 JSON 格式:
            {output_format}

            其中，"is_complete"字段表示当前回答是否是对用户原始请求的详细解答，"0"表示否，"1"表示是。当"is_complete"为"0"时，"response"字段中写入问题列表；当"is_complete"为"1"时，"response"字段中写入对用户原始输入的详细解答。

            用户的原始请求是：
            {original_request}

            请注意，每次回答时你都需要根据知识库内容仔细判断用户输入的信息是否充分、是否包含回答原始请求所需的完整信息。

            如果信息不够充分，你不能给出详细答案，"is_complete" 字段填入"0"，并在"response" 字段中列出需要用户回答的问题，以确定用户偏好、获取额外信息。比如在安装软件时通常会根据用户的不同偏好选择跳转到不同的安装步骤执行，根据操作系统、性能测试需求、网络环境等内容选择不同的安装方式和工具使用，等等。你要根据用户的软硬件环境并结合知识库内容，为用户提供合适的操作指导。
            在每轮对话中，你应该判断用户是否回答了你历史对话中列出的所有问题，若用户回答不全面，你应该分析用户输入，并根据知识库的内容继续判断还需要获取哪些信息并向用户提问，若用户对你提出的问题有其他疑问，你应该基于历史对话和知识库内容来作答或提供选项帮助用户回答你的问题，这时由于你的回答不是对用户原始请求的回答内容，此时"is_complete" 字段填入"0"，"response" 字段中根据知识库内容继续列出需要用户回答的问题，不断与用户对话获取完整回答所需的必要信息。

            经过0轮或多轮与用户的循环对话后，你总结用户提供的所有内容，当你判断认为自己所获取的信息足够充分、能够详尽的回答用户的原始请求、回答内容不包含非确定选择或可选选项时，你输出详细的答案，"is_complete" 字段填入"1"，"response" 字段中填入对用户原始问题的详细回答。
            注意**"response"字段的内容只能来源于知识库，必须按照知识库内容原文输出，输出的每个步骤具体到执行命令**，输出内容要全面，包括前置条件，如软硬件环境、编译环境、配置必要的源、数据盘搭建、依赖包安装等，以及后置验证，如配置文件、初始化和启动等。

            请注意，你不需要针对你输出的内容和用户确认是否需要调整，直接输出即可。

            你的每次回答需要考虑聊天历史。你的最后一次回答中的 "is_complete" 字段一定是"1"。
        """
        assistant_config = {
            "language": "Chinese",
            "prompt": {
                "variables": [
                    {"key": "knowledge", "optional": False},
                    {"key": "output_format", "optional": False},
                    {"key": "original_request", "optional": False},
                ],  # optional参数必须填写
                "prompt": instruction,
            },
        }
        assistant.update(assistant_config)

        # ret=assistant.list_sessions(name=session_name)
        # if len(ret)==0:
        #     session = assistant.create_session(session_name)
        # else:
        #     session=assistant.list_sessions(name=session_name)[0]
        session = assistant.create_session(session_name + " " + plan_num)

        message = original_request
        user_input = ""
        while True:
            try:
                gen = session.ask(
                    message,
                    stream=False,
                    output_format=output_format,
                    original_request=original_request,
                )
                answer = next(gen)  # Trigger generator execution
            except StopIteration as e:
                answer = e.value  # Extract actual return value from exception

            response = answer.content
            print("RAG generator:")
            print(response)  # Output content normally
            dict_json = json.loads(response)
            if dict_json["is_complete"].strip() == "1":  # 关闭显示引文
                return dict_json["response"], user_input
            elif dict_json["is_complete"].strip() == "0":
                question = input(
                    "\n==================== User =====================\n> "
                )
                self.log_file.write(question + "\n\n")
                self.log_file.flush()
                message = question
                user_input += question
                continue
            else:
                continue

    def planning_layer(
        self,
        message: str,
        original_request: str,
        planner_thread: Thread,
        error_message: str = "",
        inspector_thread: Thread = None,
        node_color: str = "lightblue",
        overall_id: str = "",
        plan_num: str = "",
        other_input: str = "",
    ):
        """
        任务/子任务/步骤规划层，调用planner agent进行结构规划。
        返回：1. 规划结果，2. 对应scheduler输入
        """
        console.rule()

        # 如果在之前的规划中rag环节获取到了用户输入的其他信息，将其拼接到original_request中
        if other_input != "":
            original_request = original_request + "\n其他信息：" + other_input

        print(f"{planner_thread.recipient_agent.name} PLANNING {overall_id}...\n")
        print(original_request)

        use_rag = os.getenv("USE_RAG")
        if use_rag=="True":
            rag_response, user_input = self.rag_flow(original_request, plan_num)
            message = message + "\n请参考运维手册内容作答：\n" + rag_response
            other_input = other_input + user_input

        # 如果有上一步出错的信息，将其拼接到message中，便于planner参考
        if error_message != "":
            message = (
                message
                + "\n\nThe error occurred when executing the previous plan: \n"
                + error_message
            )
        # 发送message给planner agent线程，获取规划结果
        planmessage = self.json_get_completion(
            planner_thread, message, original_request, inspector_thread
        )
        print(f"THREAD output:\n{planmessage}")
        planmessage_json = json.loads(planmessage)
        plan_json = {}
        plan_json["main_task"] = original_request
        plan_json["plan_graph"] = planmessage_json
        # self.json2graph(planmessage, "TASK_PLAN", node_color)
        return planmessage, json.dumps(plan_json, ensure_ascii=False), other_input

    def task_optimizing_layer(
        self,
        message: str,
        original_request: str,
        optimizer_thread: Thread,
        overall_id: str = "",
    ):
        """
        任务细化层，调用能力群细化agent进行任务细化。
        返回：细化结果
        """
        console.rule()
        print(f"{optimizer_thread.recipient_agent.name} OPTIMIZING {overall_id}...\n")
        # print(original_request)

        # 发送message给optimizer agent线程，获取任务细化结果
        optimize_message = self.json_get_completion(
            optimizer_thread, message, original_request
        )
        print(f"THREAD output:\n{optimize_message}")
        return optimize_message

    def json2graph(self, data, title, node_color: str = "blue"):
        """
        可视化任务流的json为流程图
        """
        import matplotlib.pyplot as plt
        import networkx as nx

        try:
            json_data = json.loads(data)
            graph = nx.DiGraph()  # 创建有向图
            heads = []
            edges = []
            layout = {}
            # 遍历json节点，构建图结构和层级
            for key in json_data.keys():
                idnow = json_data[key]["id"]
                layout[idnow] = 0
                if json_data[key]["dep"] == []:
                    heads.append(idnow)
                else:
                    for id in json_data[key]["dep"]:
                        edges.append((id, idnow))
                        layout[idnow] = max(layout[idnow], layout[id] + 1)
            # 分层收集节点
            layers = {}
            for key in layout.keys():
                layerid = layout[key]
                if layerid not in layers:
                    layers[layerid] = []
                layers[layerid].append(key)
            print(layers)
            for layer, nodes in layers.items():
                graph.add_nodes_from(nodes, layer=layer)
            graph.add_edges_from(edges)
            # 用networkx多分区布局画图
            pos = nx.multipartite_layout(graph, subset_key="layer")
            nx.draw(
                graph, pos=pos, with_labels=True, node_color=node_color, arrowsize=20
            )
            plt.title(title)
            plt.show()
        except json.decoder.JSONDecodeError:
            print("WRONG FORMAT!")
            return

    def json_get_completion(
        self,
        thread: Thread,
        message: str,
        inspector_request: str = None,
        inspector_thread: Thread = None,
    ):
        """
        发送消息给某个agent线程并确保返回json格式，必要时通过inspector人工/自动检查
        """
        flag = False
        count_flag_false = 0
        original_message = message
        while True:
            # 1. 先请求一次agent输出
            res = thread.get_completion(message=message, response_format="auto")
            response_information = self.my_get_completion(res)

            # 2. 尝试从返回内容解析json
            flag, result = self.get_json_from_str(message=response_information)
            # print(f"THREAD output:\n{result}")
            if flag == False:
                count_flag_false += 1
                print(f"THREAD output:\n{result}")
                # 没找到json，构造提示重新请求agent
                message = (
                    "用户原始输入为: \n```\n"
                    + original_message
                    + "\n```\n"
                    + "你之前的回答是:\n```\n"
                    + result
                    + "\n```\n"
                    + "你之前的回答用户评价为: \n```\n"
                    + "Your output format is wrong."
                    + "\n```\n"
                )
                if count_flag_false <= 3:
                    continue
                else:
                    return json.dumps({})

            # 3. 如果有inspector，需额外走一轮人工/自动审核
            if inspector_thread is not None:
                # seek for inspector's opinion
                inspector_type = os.getenv("DEBUG_INSPECTOR_TYPE")
                if (
                    inspector_type is not None and inspector_type == "off"
                ):  # 不使用inspector
                    return result

                if flag == True:
                    inspect_query = {
                        "user_request": inspector_request,
                        "task_graph": json.loads(result),
                    }
                else:
                    inspect_query = {
                        "user_request": inspector_request,
                        "task_graph": result,
                    }
                inspector_res = inspector_thread.get_completion(
                    message=json.dumps(inspect_query, ensure_ascii=False),
                    response_format="auto",
                )
                inspector_result = self.my_get_completion(inspector_res)
                print(inspector_result)
                __ = self.get_inspector_review(inspector_result)
                # 如果需要人工审核，由用户决定
                if (
                    inspector_type is None or inspector_type == "user"
                ):  # inspector回复后由用户决定
                    user_advice = input(
                        'User: ["agree": You agree with inspector.\n"YES": You agree with planner, and you should input your advice.\n"NO": You disagree with planner, and you should input your advice.]\n'
                    )
                    if user_advice != "agree":
                        explain = input("explain: ")
                        inspector_result = json.dumps(
                            {"review": user_advice, "explain": explain}
                        )
                        __ = self.get_inspector_review(inspector_result)
                # 审核通过则返回，否则要求重新输出
                if __ == True:
                    return result
                message = (
                    "用户原始输入为: \n```\n"
                    + original_message
                    + "\n```\n"
                    + "你之前的回答是:\n```\n"
                    + result
                    + "\n```\n"
                    + "你之前的回答用户评价为: \n```\n"
                    + inspector_result
                    + "\n```\n"
                )
                continue
            # 4. 没有inspector直接返回
            return result

    def get_inspector_review(self, message: str):
        """
        检查inspector给的结果是否通过（review为YES即通过）
        """
        try:
            json_res = json.loads(message)
            return json_res["review"] == "YES"
        except:
            yes_str = "YES"
            try:
                yes_index = message.index(yes_str)
                return True
            except ValueError:
                return False

    def get_json_from_str(self, message: str):
        """
        从字符串中提取json，支持带markdown代码块格式
        返回：(是否找到json, json字符串)
        """
        # try:
        #     json_res = json.loads(message)
        #     return True, message
        # except json.decoder.JSONDecodeError:
        #     # 尝试从markdown代码块中截取
        #     start_str = "```json\n"
        #     end_str = "\n```"
        #     try:
        #         start_index = message.rfind(start_str) + len(start_str)
        #         end_index = message.index(end_str, start_index)
        #         return True, message[start_index: end_index]
        #     except ValueError:
        #         return False, message

        # 1. 尝试直接解析
        try:
            json_res = json.loads(message)
            return True, message
        except json.decoder.JSONDecodeError:
            pass
        # 2. 尝试用正则匹配代码块
        match = re.search(r"```json\s*(\{.*?\})\s*```", message, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                json_res = json.loads(json_str)
                return True, json_str
            except Exception:
                return False, json_str
        # 返回False和原始消息
        return False, message

    def my_get_completion(self, res):
        """
        消耗生成器res，返回其最终返回值（即StopIteration.value）
        """
        while True:
            try:
                next(res)
            except StopIteration as e:
                return e.value

    def langgraph_test(self, repeater: Agent, rander: Agent, palindromist: Agent):
        from typing import Annotated

        from langchain_community.tools.tavily_search import TavilySearchResults
        from langchain_openai import ChatOpenAI
        from langgraph.graph import END, START, StateGraph
        from langgraph.graph.message import add_messages
        from typing_extensions import TypedDict

        class State(TypedDict):
            # Messages have the type "list". The `add_messages` function
            # in the annotation defines how this state key should be updated
            # (in this case, it appends messages to the list, rather than overwriting them)
            messages: Annotated[list, add_messages]

        graph_builder = StateGraph(State)

        repeater_thread = Thread(self.user, repeater)
        rander_thread = Thread(self.user, rander)
        palindromist_thread = Thread(self.user, palindromist)
        from langchain_core.messages.ai import AIMessage

        def chatbot_0(state: State):
            message = state["messages"][-1]
            res = rander_thread.get_completion(message.content)
            ans = self.my_get_completion(res)
            return {"messages": [AIMessage(ans)]}

        def chatbot_1(state: State):
            message = state["messages"][-1]
            res = repeater_thread.get_completion(message.content)
            ans = self.my_get_completion(res)
            return {"messages": [AIMessage(ans)]}

        def chatbot_2(state: State):
            message = state["messages"][-1]
            res = palindromist_thread.get_completion(message.content)
            ans = self.my_get_completion(res)
            return {"messages": [AIMessage(ans)]}

        graph_builder.add_node("rander", chatbot_0)
        graph_builder.add_node("repeater", chatbot_1)
        graph_builder.add_node("palindromist", chatbot_2)

        graph_builder.add_edge(START, "rander")
        graph_builder.add_edge("repeater", END)
        graph_builder.add_edge("palindromist", END)

        def route(
            state: State,
        ):
            if isinstance(state, list):
                ai_message = state[-1]
            elif messages := state.get("messages", []):
                ai_message = messages[-1]
            else:
                raise ValueError(f"No messages found in input state: {state}")
            import re

            try:
                print(ai_message)
                text = ai_message.content
                number = re.findall(r"\d+\.?\d*", text[-1])
                if int(number[-1]) < 5:
                    return "repeater"
                return "palindromist"
            except:
                return "repeater"

        graph_builder.add_conditional_edges(
            "rander",
            route,
            {"repeater": "repeater", "palindromist": "palindromist"},
        )
        graph = graph_builder.compile()
        import io

        import matplotlib.pyplot as plt
        from PIL import Image

        # ... (你的 graph 对象和相关代码) ...
        image_data = graph.get_graph().draw_mermaid_png()  # 获取图像字节流数据
        img = Image.open(io.BytesIO(image_data))  # 使用 PIL 读取 PNG 图像
        plt.imshow(img)  # 使用 matplotlib 显示图像
        plt.axis("off")  # 可选：隐藏坐标轴
        plt.show()

        def stream_graph_updates(user_input: str):
            for event in graph.stream({"messages": [("user", user_input)]}):
                for value in event.values():
                    print("Assistant:", value["messages"][-1].content)

        while True:
            try:
                user_input = input("User: ")
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                stream_graph_updates(user_input)
            except:
                # fallback if input() is not available
                user_input = "What do you know about LangGraph?"
                print("User: " + user_input)
                stream_graph_updates(user_input)
                break
