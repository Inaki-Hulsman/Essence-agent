from app.services.observability import langfuse


# -----------------------
# 🤖 AGENT PROMPTS
# -----------------------

INITIAL_INPUT = "Say hello to the user and briefly introduce yourself. Use the language {language}"

# ----------------------------------------------------------------------------------------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a VOICE assistant that helps fill out forms.

You have access to the following tools:
{tools}

When the user provides information or asks for something related to the form, use the appropriate tools.
If it’s just a general conversation or question, respond directly without using tools.
Do not use asterisks to highlight text; do not use Markdown, bold, or italics.
Keep the conversation focused on helping the user complete the form by asking about sections that are still incomplete.

CURRENT FORM STATUS: {form}"""

# ----------------------------------------------------------------------------------------------------------------------------------------------------------

ROUTER_PROMPT = """Analyze the message and the context. Decide if you need a tool.

Available tools: {tool_names}

Respond with JSON indicating whether you need a tool and which one. If you don't need any, set tool_name = "none"."""

# ----------------------------------------------------------------------------------------------------------------------------------------------------------

EXECUTOR_PROMPT = """Based on the user's message and history, generate the exact arguments to call: {tool_name}

Description: {tool_description}
Required parameters: {required_params}

Generate ONLY the arguments in JSON, without any additional text."""



# -----------------------
# 📋 FORM MANAGEMENT PROMPTS
# -----------------------

ECTRACT_INFO_PROMPT = """[ROLE]
You are an assistant that extracts information from movie descriptions given by the user.

[CURRENT FORM STATE]
{form}

[RECENT MESSAGES]
{chat}

[INSTRUCTIONS]
Complete the form fields the user is talking about with the given information . You can only fill in the fields whose key is "value"
if you modify "value" also change the "status" of that field to "agent". Never modify "description" from the current form state.

If not specified, return null.
Only return valid JSON.

if the user has attached an image as reference, analyze the image to get information of the fields mentioned by the user and add it to the form.
Also set the "status" of that field to "image_ref" (even if it is already fulfilled)"""

#----------------------------------------------------------------------------------------------------------------------------------------------------------

CORRECT_FIELDS_PROMPT = """A model has extracted this set of fields from a dictionary based on the user's message. However, they are incorrect because they must belong to a predefined list.

[FIELDS EXTRACTED BY THE MODEL]:
{actual_fields}

[LIST OF PREDEFINED FIELDS]:
{posible_fields}

[INSTRUCTIONS]:
Returns a list with the corrected fields based on what the user originally requested.
They must always be values from the list of predefined fields.
Always returns a valid list.

[USER MESSAGE]:
{message}"""



PROMPT_SCHEMA = {
    "initial_input" : INITIAL_INPUT,
    "system_info" : SYSTEM_PROMPT,
    "tool_executor": EXECUTOR_PROMPT,
    "agent_router": ROUTER_PROMPT,
    "Extract_section_info" : ECTRACT_INFO_PROMPT,
    "correct_fields" : CORRECT_FIELDS_PROMPT
}

####### VLLM AGENT PROMPTS ####### 

def get_chat_prompt(name: str, role: str, **args):

    try:
        prompt = langfuse.get_prompt(name)
        compiled_prompt : list = prompt.compile(**args) # type: ignore
        return compiled_prompt
        
    except Exception as e:
        print(f"Error al cargar el prompt '{name}': {e}. Usando fallback...")
        return [{"role": role, "content": PROMPT_SCHEMA[name].format(**args)}]


def get_text_prompt(name: str, **args):

    try:
        prompt = langfuse.get_prompt(name)
        return prompt.compile(**args)
        
    except Exception as e:
        print(f"Error al cargar el prompt '{name}': {e}. Usando fallback...")
        return PROMPT_SCHEMA[name].format(**args)



def get_initial_input_prompt(language = "english"):
    try:
        prompt = langfuse.get_prompt("initial_input")
        return prompt.compile(language = language)
    except:
        print("error al cargar el prompt 'initial_input' desde langfuse. Utilizando el fallback...")
        return INITIAL_INPUT.format(language = language)

def get_system_prompt(form_text : str, tools : str) -> list:
    try:
        prompt = langfuse.get_prompt("system_info")
        compiled_prompt : list= prompt.compile(form = form_text, tools = tools) # type: ignore
        return compiled_prompt
    except:
        print("error al cargar el prompt 'initial_input' desde langfuse. Utilizando el fallback...")
    return [{"role": "system", "content": SYSTEM_PROMPT.format(form=form_text, tools=tools)}]

def get_router_prompt(tool_names):
    return [{"role": "user","content": ROUTER_PROMPT.format(tool_names=", ".join(tool_names))}]

def get_executor_prompt(tool_name, tool_description, required_params):
    return [{
        "role": "user",
        "content": EXECUTOR_PROMPT.format(
            tool_name=tool_name,
            tool_description=tool_description,
            required_params=required_params
        )
    }]

###### BASIC LLM PROMPTS #######

def get_extract_info_prompt(new_form, user_message):
    prompt = langfuse.get_prompt("Extract_section_info")
    compiled_prompt : list= prompt.compile(form=new_form,chat=user_message) # type: ignore
    return compiled_prompt


def get_correct_fields_prompt(actual_fields, posible_fields, message):
    prompt =  langfuse.get_prompt("correct_fields")

    compiled_prompt : list = prompt.compile(
        actual_fields = actual_fields,
        posible_fields=posible_fields,
        message=message
    ) # type: ignore

    return compiled_prompt
