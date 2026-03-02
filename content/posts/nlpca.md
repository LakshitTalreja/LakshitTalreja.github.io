---
title: "NLPCA Mark Kramer (1991)"
date: "2025-2-15"
layout: "post"
tags:
    - "machine learning"
    - "research"
    - "AIEP"
    - "Cirem"

---

[Nonlinear Principal Component Analysis Using Autoassociative Neural Networks](https://share.google/dXHx9mEI8M8ztG2Mj)
Mark A. Kramer
February 1991

---

# Introduction

Many great engineering journeys begin with a spark of curiosity. For me, that spark happened during a course I took on Neural Networks taught by two of my favourite seniors [Andey Hemanth](https://github.com/Andy34G7) and [Maaya Mohan](https://github.com/maayamohan).
They inspired or rather forced us to read research papers on machine learning and not just read them but understand the model architecture and the math that goes on behind these models.

This specific paper on NLPCA(Nonlinear Principal Component Ananlysis) was a paper that a friend of mine picked up after the course had ended and even presented his explanation of the paper at a [fireside talk](https://www.youtube.com/live/eTsNtSnOP7U?si=KLO7S8UGcuZacPuW). His interest and explanation is why I picked up this paper.

In this blog I'm going to break down everything mentioned in the paper and my interpretation of it, I will do my best to explain the math and the model architecture whilst also keeping it simple enough to understand.

---

# What is this paper about?

The reduction of a dataset from its superficial to intrinsic dimensions(the minimum number of free parameters needed to approximately describe a data set) is the focus of this paper.

Whenever we need to represent data on a graph it's always better to have fewer dimensions, and this paper's goal is to find the minimun number of dimensions that we can repsresent the data with and the primary goal of this paper was to achieve this but for non linear functions unlike the PCA models.

Before we dive into NLPCA(Nonlinear Principal Component Ananlysis) lets discuss PCA(Principal Component Ananlysis), *PCA is a technique for mapping multidimensional data into lower dimensions with minimal loss of information.* Now if you didn't get a few words that's alright but the idea of PCA is to take large datasets and reduce them into something that is easier for us to understand and for the model to run on. But it does so only with linear functions.

### How is it done though?

We consider a matrix Y(nxm) as our input data, T(nxf) as the score matrix and P(mxf) as the loading matrix and also E(nxm) as the matrix of residuals where 
- n = no. of observations
- m = no. of variables 
- f = no. of factors 

> What is the score and the loading matrix
>> Score matrix is the transformed data, the data in the new compressed space.
>> Loading matrix is the connection between our original data and the new principal components. It tells us how much each original value connects and contributes to the new components.

**Y = TP^T + E**
This is the fundamental equation of a PCA, the goal is to minimise E for the given number of factors.

How do we measure E?
A' - A = E where A represnts a row of Y and A' is the reconstructed measurement vector, that is the vector that we recieve after the data has gone through the encoder and then the decoder.
*Note: the output from the encoder is the input for the decoder.*

## What do we do when our data isn't linear?

That is exactly when NLPCA comes in ,the main difference between PCA and NLPCA is that the latter involves non linear mappings between the original and reduced dimension spaces.
NLPCA will describe the data with greater accuracy and/or fewer factors than PCA, The NLPCA method uses Artifical neural networks(ANN) training procedures to generate non linear features.

To define the model it is spilt into two parts, the encoder(G) and the decoder(H).


### Encoder 
A nonlinear vector G is introduced, it contains f individual nonlinear functions G = [G1,G2,....Gi], analogous to P such that Ti represents the ith element of T.
$ T_i = G_i(Y) $

### Decoder 
Another non linear vector H is introduced, H = [H1,H2,...Hi] and Y' is the reconstruced measurement vector.

$ Y'_j = H_j(T) $


The loss of information is given by E and is expressed by Y - Y'(difference in input and final output).
E = Y - Y'

---

To generate G and H vectors, a basis function approach is used.
\[
v_k = \sum_{j=1}^{N_2} W_{jk2} \, \sigma \left(
\sum_{i=1}^{N_1} w_{ji1} u_i + \theta_j
\right)
\]
Now that is a heavy equation so lets break it down.
- It defines a model with N1 inputs 
- a hidden layer with N2 nodes 
- sigma(x) is any continuous and monotonically increasing function. One such fuction is the sigmoid function that is used here to reduce the data between 0 and 1. 
- $ w_ijk $ is the weight on the connection from node i in layer j in layer k+1.
- θ are nodal biases, treated as adjustable parameters like weights

# Model Architecture

**To achieve universal fitting properly, exactly one layer of sigmoidal nodes and two layers of weighted connections are required**
The ability of the neural network to fit arbitrary nonlinear functions depends on the presence of a hidden layer with non linear nodes. This statement is something I picked straight out of the paper, the statement is very easy to understand and extrememly cruicial to how they defined the model and why they chose to do so.

A network lacking a hidden layer but including sigmoidal nonlinearlitiees in the output layer is only capable of generating multivariable sigmoidal functions, i.e., linear functions compressed in the range(-1,1) by the sigmoid. **This statement reiterates the need for a hidden layer.**
Neither network without a hidden layer is compatible with the goal of representing arbitrary nonlinear functions.

![Network Architecture](/assets/images/NLPCA/Screenshot%202026-03-01%20033847.png)

## Bottle-neck layer 
What is it, well it's the layer between the encoder and the decoder layers or the layer between the mapping and demapping layers.

*Note: the bottle-neck layer consists only of linear nodes*

But why do we need a bottle neck layer, well lets consider a case where we remove the mapping and the demapping layers and are left with only the input, output and bottleneck layers .
The nodes of the bottle neck layer are linear and thus the model would correspond exactly to the PCA model. If the nodes were sigmoidal on the other hand the G and H vectors would be **severly contrained**.
*Therefore, the performance of an autoassociative network with only one internal layer of sigmoidal nodes is often no better than linear PCA.*

This lead to the conclusion that to achieve non linear feature extraction 3 hidden layers(mapping,demapping and bottle-neck) are essential.

# Examples

The paper has two examples of NLPCA with comparisons to PCA. I will be breaking down the first one.
### Dataset 
A dataset consisting of two observed variables y1 and y2 driven by an underlying parameter θ
- $ y_1 =0.8(sinθ) $
- $ y_2 =0.8(cosθ) $
- θ = U[0,2pi]

### Parameters 
Three different methods were applied to the same dataset to compare and determine the best one factor representation 
- PCA
- ANN with one hidden layer(only bottleneck layer) 
- NLPCA

![Parameters](/assets/images/NLPCA/Screenshot%202026-03-01%20040708.png)
The table represents the different paramters along with the Error E.
**The recontruction error in PCA and the ANN is much higher than in the NLPCA**
The only difference in the ANN and the NLPCA is the number of hidden layers and this reiterated the need for 3 hidden layers.

We can also note that after increasing the mapping nodes to 4, the error is almost a constant and the FPE along with the AIC indicate that 4 is the ideal number of mapping nodes.

### Reconstruction 
![Reconstructed data from one factor](/assets/images/NLPCA/Screenshot%202026-03-01%20041216.png)
This image represnts the 3 different methods, Due to its linea rapproach the PCA method yeild a straight line. The ANN is only marginally better than the PCA but due to no hidden layers it can only produce features that are linear combinations of input compressed by sigmoid.
The reconstruction by the ANN is essentially linear but with a slight *sigmoidal curve*.
On the other hand the NLPCA method reconstructs the data from one nonlinear factor with greater accuracy.

# Conclusion 
This paper not only shows us that by simply adding depth and non-linear mapping layers, we can capture circular or curved patterns that traditional PCA would completely miss but also lays the groundwork for the modern autoencoders that we are familar with.

### Thank you for reading!!