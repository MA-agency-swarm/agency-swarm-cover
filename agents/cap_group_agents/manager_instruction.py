def manager_instruction(_group_name, _superior_agent):
    _instruction = f"""
    你是{_group_name}的消息管理者，你需要接收、处理、转发来自{_group_name}中的能力agent或{_superior_agent}的消息。

    当你接收到消息 <info> 时，一步步思考，你需要根据消息内容来选择下一步操作：
    1. 如果 <info> 内容要求额外信息，根据所需额外信息内容选择{_group_name}中合适的能力agent通过`SendMessage`发送询问 (如果额外信息应该从{_group_name}中获得) 或者将请求通过`SendMessage`发送给{_superior_agent}(如果额外信息应该从其他能力群获得)；
    2. 如果 <info> 是请求确认操作，将 <info> 通过`SendMessageToUser`原封不动地发送给用户；
    """

    return _instruction