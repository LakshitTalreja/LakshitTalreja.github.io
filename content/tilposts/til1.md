---
title: "LLM Optimisation Part One"
date: "2025-05-18"
layout: "tilpost"
tags:
    - "machine learning"
    - "research"
    - "LLM"

---

# Introduction 
Before I dive into today's topic, I want to address what this page is. In a nutshell it is a section of my site I will be using to add my thoughts and learnings *daily*. Just something to hold me accountable and to document my learnings and progress.

# LLM optimisation 
Why this topic? 
Well the answer is a little stupid to be honest but because someone sent me this link(Hemanth) and I opened it and read like 5 lines and told myself I'll get back to it soon but honestly havent opened it since and it remained in my open tabs(a problem i should really solve) so I decided to read it today.

[The article](https://medium.com/@dinukajkdy/decoding-the-dragon-why-llm-performance-is-a-two-part-problem-49d368a357a5)

The whole point of this blog is to address handling multiple users using your LLM and optimising the results.
It breaks it down into "two distinct computational phases, each with its own unique bottleneck."

## Architectural Foundation
Most modern generative LLMs use a decoder only transformer architecture and this design is built upon the self attention model which calculates the importance of each token wrt to every other token.

> The core challenge stems from the complexity of this attention mechanism:O(N²). 

This is the 3rd sentence and I already feel lost so I searched it up because I do not understand that notation though I have seen it a few times before.
And after searching and going through a few sites this is what I learned, 
[Time complexity](https://medium.com/@ryassminh/time-complexity-in-ml-ensuring-model-performance-with-growing-data-sizes-42007e5b7305)
I refered to this medium blog to understand time complexity and the big O notation.
> Time complexity measures the amount of computational time an algorithm takes to run as a function of the size of its input data (denoted as n). It provides a theoretical estimate of the running time, helping to predict performance and scalability. 

This is honestly pretty self explanatory but I do want to add it here for me to refer to later.
### The Big O 
O(f(n)) is the upper bound of the time complexity where f(n) is the the function that describes how the runtime scales with the *input size n*.
Few examples - 
O(1) - Execution does not depend on input size
O(n) - Time increases proportionally with input size
O(n2) - Time increases proportionally to the square of the input size 

ok coming back to the first blog,
>  As the input sequence length (N) doubles, the computation effort quadruples. This quadratic explosion is what makes handling long contexts expensive and slow, and it directly shapes the two phases of inference.


**This makes sense to me now**

To solve this issue engineers have implemented 2 solutions 
- Multi Query Attention - Multiple heads share the same key and value matrices reducing the memory footprint.
- Grouped Query Attention - A compromise between the original MHA and the highly optimized MQA, offering a better balance of latency and quality.

The GQA attention made a little less sense to me so I'll look into it later.

## Two critical phases of LLM optimisation 
### Phase 1 - The Prefill Phase (Input)
![Alt Text](/assets/images/TIL/1.webp)

This is an image from the blog breaking down the two phases.
This phase handles the user input or the prompt.
> During Prefill, the entire prompt is processed in a single, large, parallel operation. Since this phase involves heavy linear algebra (MatMuls) over a long sequence, the process is limited by the raw computational power (FLOPS) of your hardware.
For the most part this is very easy to understand and essentially how fast the LLM processes our input or prompt depends on our hardware due to the raw computational power.

### Phase 2 - The Decoding Phase 
This is the phase where the model generates the answers we see in the form of tokens.
> The critical component here is the KV Cache (Key and Value tensors). After the Prefill phase, the K and V matrices calculated from the input are saved in GPU memory. For every subsequent token generated, the model must retrieve all of the past tokens’ K and V values from memory to maintain context. This constant retrieval makes the Decode phase limited by the memory bandwidth (how fast data can be read from the GPU memory), not the raw compute power.

Honestly both of these sections are very easy to understand but I will be adding them here for me to refer to later and for the blog to be more complete and make more sense.

## Metrics 

### Time to first token: 
The time taken from the moment the prompt is sent to the moment the first output token is generated.
If your TTFT is slow, your issue is likely compute-bound. You need optimizations that accelerate large MatMuls, like highly optimized kernels (e.g., FlashAttention) or tensor parallelism.

### Time-Between-Tokens (TBT)
The average time taken to generate any subsequent token after the first one. Also known as “per-token latency.”
If your TBT is slow, your issue is memory-bandwidth-bound. You need optimizations focused on KV Cache management, such as quantization (reducing the size of the cache) or efficient batching.

### Overall Throughput (Tokens Per Second, or TPS)
The total number of tokens (input + output) processed per second across all concurrent requests.
The engine’s overall capacity to handle load. TPS is often the target metric when using techniques like continuous batching

## Conclusion 
Though a lot of what I wrote today was copy pasted from the blog I was refering to, I still did end up learning a lot and I will continue to do this daily and hopefully get better at writing my understandings and learnings.
The next step would be to read part 2 of this blog which would cover batching and paralleism but unfortunately I have 2 tests tomorrow and I need to study for them.

*Das Ende*
