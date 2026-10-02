# EdgeAI Source Map

This file is the durable source strategy for EdgeAI. It separates discovery signals from sources strong enough to support publication.

## Core rule

EdgeAI should be early, but not credulous.

- **Primary**: official lab, project, paper, release, changelog or repository. Strongest evidence.
- **Independent**: technically credible analyst, evaluator, researcher or publication. Use for verification/context.
- **Signal**: directory, launch board, newsletter, community or aggregator. Excellent for discovery, but should trigger investigation rather than establish fact by itself.
- **Community**: GitHub discussions, Hacker News, Reddit and similar. Useful for finding emerging issues and real-world reactions; never enough alone for a factual breaking article.

A normal EdgeAI breaking article should aim for one primary source plus at least one independent corroborating source when available. Rumours remain labelled and do not become CONFIRMED without primary evidence.

## 1. Fast discovery and tool radar

These are especially important for catching small tools and niche launches before mainstream press notices them.

- FutureTools — https://futuretools.io/ — curated AI news and tools; high-value discovery signal.
- Futurepedia — https://www.futurepedia.io/ — large AI tool directory plus newsletter/archive.
- There's An AI For That — https://theresanaiforthat.com/ — very broad task-based tool discovery.
- TopAI.tools — https://topai.tools/ — large, daily-updated tool directory with new/free/trending sections.
- Toolify — https://www.toolify.ai/ — large-volume AI tool directory and discovery source.
- Product Hunt AI — https://www.producthunt.com/topics/artificial-intelligence?order=recent_launches — new AI product launches.
- Product Hunt AI Agents — https://www.producthunt.com/categories/ai-agents?order=recent_launches — agent-specific launch radar.
- Hugging Face Blog / Community Articles — https://huggingface.co/blog — model, dataset and open-source ecosystem signals.
- Hugging Face Models — https://huggingface.co/models — model-release discovery; needs popularity/author filters.
- Hugging Face Papers — https://huggingface.co/papers — research discovery and discussion.

**Policy:** tool directories and Product Hunt are discovery-only. Paid/featured placement must never increase story importance. EdgeAI should follow through to the tool's own website, documentation, GitHub repo or announcement before publishing.

## 2. Independent writers and newsletters

These are valuable because they frequently surface material before broad technology media and add technical judgement.

- Simon Willison's Weblog — https://simonwillison.net/ — exceptionally strong LLM/tool/agent release commentary.
- Latent Space / AINews — https://www.latent.space/ — daily/technical AI engineering coverage.
- Interconnects — https://www.interconnects.ai/ — frontier/open models, post-training and ecosystem analysis.
- Ahead of AI / Sebastian Raschka — https://magazine.sebastianraschka.com/ — deep technical LLM research and architecture analysis.
- Sebastian Raschka LLM index — https://www.sebastianraschka.com/topics/large-language-models/ — concise running technical notes.
- One Useful Thing / Ethan Mollick — https://www.oneusefulthing.org/ — applied frontier-model analysis.
- Last Week in AI — https://lastweekin.ai/ — broad weekly research/news digest.
- Import AI / Jack Clark — https://importai.substack.com/ — AI research and policy context.
- AI Snake Oil — https://www.aisnakeoil.com/ — sceptical analysis and hype checking.
- The Batch — https://www.deeplearning.ai/the-batch/ — research and industry digest.
- Data Elixir — https://dataelixir.com/ — ML/data-science links and niche technical discoveries.
- Drew Bredvick field notes — https://drew.tech/newsletter — smaller applied-AI signal source.
- TLDR AI — https://tldr.tech/ai — dense technical daily discovery.
- The Rundown AI — https://www.therundown.ai/ — broad daily AI news/tools signal.
- Ben's Bites — https://bensbites.com/ — builder/startup/product signal.

## 3. Primary frontier labs and model developers

- OpenAI News — https://openai.com/news/
- Anthropic Newsroom — https://www.anthropic.com/news
- Anthropic Alignment Science — https://alignment.anthropic.com/
- Google DeepMind — https://deepmind.google/discover/blog/
- Google AI / Technology — https://blog.google/technology/ai/
- Google Developers Blog — https://developers.googleblog.com/
- Meta AI — https://ai.meta.com/blog/
- SpaceXAI/xAI News — https://x.ai/news
- Mistral AI News — https://mistral.ai/news/
- Cohere Research — https://cohere.com/research
- AI21 Blog — https://www.ai21.com/blog/
- Ai2 Blog — https://allenai.org/blog
- NVIDIA AI Blog — https://blogs.nvidia.com/blog/category/generative-ai/
- Microsoft Research Blog — https://www.microsoft.com/en-us/research/blog/

## 4. Non-US and smaller model labs

These are essential because open and regional labs increasingly release important models before Western mainstream coverage catches up.

- Qwen / Alibaba — https://qwenlm.github.io/blog/
- DeepSeek GitHub — https://github.com/deepseek-ai — release/repository signal.
- Kimi / Moonshot Research — https://www.kimi.com/en/blog/
- MiniMax Research — https://www.minimax.io/blog
- Z.ai / GLM — https://z.ai/blog
- Sakana AI — https://sakana.ai/blog/
- Nous Research — https://nousresearch.com/
- Together AI Research — https://www.together.ai/research-blog
- Together AI Blog — https://www.together.ai/blog
- ModelScope — https://modelscope.cn/ — Chinese open-model ecosystem signal.

## 5. Model benchmarks, evaluation and real-world adoption

- Artificial Analysis Changelog — https://artificialanalysis.ai/changelog — rapid new-model benchmark signal.
- Artificial Analysis Articles — https://artificialanalysis.ai/articles — launch analysis and benchmark context.
- OpenRouter Rankings — https://openrouter.ai/rankings — real-world model usage/adoption signal.
- OpenRouter Image Rankings — https://openrouter.ai/rankings/image — image-model adoption signal.
- LM Arena — https://lmarena.ai/ — comparative model preference/evaluation signal.
- MLCommons Insights — https://mlcommons.org/insights/ — MLPerf and standardised benchmark releases.
- METR Updates — https://metr.org/blog/ — independent frontier capability and risk evaluations.
- Epoch AI Gradient Updates — https://epoch.ai/gradient-updates — compute, capability, economics and trend analysis.
- Epoch AI Trends/Data — https://epoch.ai/trends — structured AI trajectory data.
- Center for AI Safety newsletters — https://safe.ai/newsletter — research/safety signal.
- Redwood Research — https://www.redwoodresearch.org/research — alignment/control/security research.
- Transluce — https://transluce.org/ — independent model-behaviour and incident research.

## 6. Open-source/local AI runtime radar

GitHub release feeds are especially valuable because they often beat news sites by hours or days.

- llama.cpp — https://github.com/ggml-org/llama.cpp/releases.atom
- Ollama — https://github.com/ollama/ollama/releases.atom and https://ollama.com/blog
- vLLM — https://github.com/vllm-project/vllm/releases.atom
- SGLang — https://github.com/sgl-project/sglang/releases.atom
- LocalAI — https://github.com/mudler/LocalAI/releases.atom and https://localai.io/blog/
- Hugging Face Transformers — https://github.com/huggingface/transformers/releases.atom
- Hugging Face Diffusers — https://github.com/huggingface/diffusers/releases.atom
- Hugging Face smolagents — https://github.com/huggingface/smolagents/releases.atom
- MLX — https://github.com/ml-explore/mlx/releases.atom
- Open WebUI — https://github.com/open-webui/open-webui/releases.atom
- LiteLLM — https://github.com/BerriAI/litellm/releases.atom
- Unsloth — https://github.com/unslothai/unsloth/releases.atom
- Axolotl — https://github.com/axolotl-ai-cloud/axolotl/releases.atom
- torchtune — https://github.com/pytorch/torchtune/releases.atom

## 7. Agents and AI coding ecosystem

- Aider — https://github.com/Aider-AI/aider/releases.atom
- Cline — https://github.com/cline/cline/releases.atom
- Continue — https://github.com/continuedev/continue/releases.atom
- OpenCode — https://github.com/anomalyco/opencode/releases.atom
- browser-use — https://github.com/browser-use/browser-use/releases.atom
- LangChain — https://github.com/langchain-ai/langchain/releases.atom
- LlamaIndex — https://github.com/run-llama/llama_index/releases.atom
- Microsoft AutoGen — https://github.com/microsoft/autogen/releases.atom
- CrewAI — https://github.com/crewAIInc/crewAI/releases.atom
- DSPy — https://github.com/stanfordnlp/dspy/releases.atom
- Pydantic AI — https://github.com/pydantic/pydantic-ai/releases.atom
- Model Context Protocol — https://github.com/modelcontextprotocol — watch specification/SDK/server releases.

## 8. Image, video, audio and creative AI

- ComfyUI releases — https://github.com/Comfy-Org/ComfyUI/releases.atom
- ComfyUI Blog — https://blog.comfy.org/
- Black Forest Labs — https://bfl.ai/blog
- Stability AI — https://stability.ai/news
- Runway — https://runwayml.com/research/
- Luma AI — https://lumalabs.ai/
- Replicate Blog — https://replicate.com/blog/ — unusually useful for newly runnable creative models; RSS/Atom available.
- ElevenLabs Research Blog — https://elevenlabs.io/blog/category/research
- Suno Blog — https://blog.suno.com/
- Udio — https://www.udio.com/ — product/release signal when public announcements are available.

## 9. Inference, hardware and infrastructure

- SemiAnalysis — https://semianalysis.com/ — deep AI compute/hardware/infrastructure analysis; some material may be paywalled.
- Modal Blog — https://modal.com/blog — inference, sandboxes, kernels and production agent infrastructure.
- Baseten Blog — https://www.baseten.co/blog/ — inference/deployment engineering.
- Fireworks AI Blog — https://fireworks.ai/blog — inference, serving and model platform developments.
- Cerebras Blog — https://www.cerebras.ai/blog
- Groq Blog — https://groq.com/blog
- Together AI Research — https://www.together.ai/research-blog
- NVIDIA AI Blog — https://blogs.nvidia.com/blog/category/generative-ai/
- Epoch AI chips/data-center datasets — https://epoch.ai/topics/chips

## 10. Research firehose

Do not send every paper to Gemini. Use keyword/author/citation heuristics first.

- arXiv cs.AI — https://export.arxiv.org/rss/cs.AI
- arXiv cs.LG — https://export.arxiv.org/rss/cs.LG
- arXiv cs.CL — https://export.arxiv.org/rss/cs.CL
- arXiv cs.CV — https://export.arxiv.org/rss/cs.CV
- arXiv stat.ML — https://export.arxiv.org/rss/stat.ML
- arXiv cs.CR — https://export.arxiv.org/rss/cs.CR — useful for LLM/agent security work when filtered.
- Hugging Face Papers — https://huggingface.co/papers

## 11. Community / early-warning signals

These should have low trust but high discovery value.

- Hacker News — https://news.ycombinator.com/
- GitHub Trending — https://github.com/trending
- GitHub releases/discussions for watched AI repos.
- Reddit communities such as r/LocalLLaMA, r/MachineLearning, r/StableDiffusion and tool-specific communities.

Community claims never publish as fact without verification.

## Source weighting recommendation

- **Priority 0 — immediate primary:** official model/release/security announcement, model card, GitHub release, paper from the project itself.
- **Priority 1 — high-value independent:** METR, Artificial Analysis, Epoch AI, MLCommons, Simon Willison, Interconnects, Ahead of AI, SemiAnalysis.
- **Priority 2 — discovery:** FutureTools, Futurepedia, Product Hunt, TopAI.tools, There's An AI For That, Latent Space/AINews, newsletters.
- **Priority 3 — community:** Hacker News, Reddit, GitHub discussions/social signals.

Discovery priority is not factual authority. A Priority-2 source may tell EdgeAI where to look first, while a Priority-0 source is what allows EdgeAI to call something confirmed.

## Cost-control rule

The radar should use cheap deterministic checks first: publication timestamp, unseen URL, source priority, keywords, repo release type, author/lab identity and duplicate fingerprints. Gemini should only inspect candidates that survive those filters. This keeps the project inside the free tier while still monitoring a large source universe.
