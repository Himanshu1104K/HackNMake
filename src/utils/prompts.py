from langchain_core.prompts import ChatPromptTemplate

DATA_PARSER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """""",
        ),
        (
            "user",
            "{data_records}",
        ),
    ]
)
