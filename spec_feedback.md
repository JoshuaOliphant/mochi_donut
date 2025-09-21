# Spec Feedback

- Let's use Chroma for the databse instead of Postgres and pgvector.
  - We can use Chroma locally for development and then consider using Chroma Cloud for production. 
- No need to use A/B testing, as I am the only user initially. Let's keep the eval process simple.
- The roadmap doesn't need times. I'll be developing this application with AI in the form of Claude Code so it will happen more quickly than expected and so will be hard to measure in advance. 
- Use JinaAI api to convert web content to markdown.
- We should generally convert content to markdown.
- Let's investigate using LangChain instead of PydanticAI for this project, particularly since they have a nice integration with Chroma. 
- We will not us Claude Opus, it is way too expensive.
- Probably we will use GPT-5 models since they are cheaper, they have a range of GPT-5 models, including a nano version that is very cheap. We should investigate the GPT-5 models and use different sizes for the appropriate task, with the intention of keeping costs low.