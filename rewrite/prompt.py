prompt_rewrite='''
You are a statistician. You currently have a dataset designed to evaluate the abstraction and modelling of statistical problems; each sample contains an input (the original statistical problem) and an output (an abstract statistical model derived from the original problem).

---

The input format is:

{
    "background": "Relevant description of the problem context (which may also contain some data)",
    "data": "The data used, presented as a table in LaTeX code",
    "question": "The core problem"
}

The abstracted statistical model includes the following four parts:  
1. Method category (method), which is the category of the statistical model used and must strictly come from the following framework (the result should be from the content within []):  

- "Data Preprocessing" includes: ["Missing Value Handling", "Outlier Handling", "Standardization", "Binning", "Transformation"].  

- "Mathematical Calculation" includes: ["Probability Space Related (e.g., number of states)", "Event Probability and Independence", "Expectation", "Minimum Sample Size Required to Achieve a Specified Probability", "Distribution Derivation", "Other"].  

- "Numerical Computation" includes: ["Obtaining Model Parameter Estimates", "Sampling from a Specified Distribution"].  

- "Descriptive Statistics" includes: ["Measures of Central Tendency", "Measures of Dispersion", "Measures of Distribution Range", "Measures of Frequency and Proportion", "Quantiles/Percentiles", "Network Graph Indicators", "Analysis and Comparison of Statistical Properties", "Other (e.g., reliability)"].  

- The "Data Distribution Modelling" section includes: ["Model Building", "MLE", "Bayesian"].

- "Data Visualization" includes: ["Distribution of Discrete Variables", "Distribution of Continuous Variables", "Relationship Between Discrete and Continuous Variables", "Relationship Between Continuous Variables", "Relationship Between Discrete Variables", "Comprehensive Comparison of Multiple Variables", "Trends Over Time", "Spatial and Geographic Visualization", "Text and Symbolic Visualization", "Stem-and-Leaf Plot", "Other Statistical Graphics"].  

- "Association Analysis" includes: ["Correlation Coefficient (One-dimensional)", "CCA (Multidimensional)", "Contingency Table"].  

- "Clustering" includes only: ["Clustering"].  

- "Dimensionality Reduction" includes only: ["Dimensionality Reduction"].  

- "Hypothesis Testing and Interval Estimation" includes: ["Independence Test", "Mean Test", "Variance Test", "ANOVA", "Distribution Test", "Proportion Test", "Likelihood Ratio Test", "Sequential Test", "Randomness", "Regression Model Parameter Test", "Analysis of Test Properties"]. (Note: Since hypothesis testing and interval estimation are two sides of the same coin, although the secondary categories below are mostly named with "test", they also include corresponding interval estimation methods.)  

- "Model Comparison (Variable Selection)" includes: ["Criterion-Based Comparison (AIC, BIC, etc.)", "Cross-Validation", "Likelihood Ratio Test", "ROC Curve (AUC), Coverage-Capture Rate Curve", "Identification of Important Variables"].  

- "Model Diagnosis" includes: ["Residual Analysis", "Goodness-of-Fit Assessment"].  

- "Model Interpretation" includes: ["Interpretation of Regression Coefficient Significance and Direction", "Interpretation of Regression Effect Size", "Interpretation of Factors Influencing Classification or Occurrence Probability", "Interpretation of Mechanisms Influencing Ordered Outcomes", "Interpretation of Variable Importance Ranking", "Interpretation of Group Heterogeneity"].  

- "Classification and Prediction" includes: ["Continuous Value Prediction", "Categorical Variable Classification", "Multi-class Classification of Ordered Variables", "Quantile Prediction", "Survival Analysis"].  

- "Time Series Analysis" includes: ["Lag Correlation Analysis", "Stationarity Analysis", "Seasonality Analysis", "Deterministic Factor Decomposition", "Volatility Analysis"].  

- "Text Data Analysis" includes: ["Tokenization", "Word Frequency Statistics", "Topic Modeling", "Sentiment Analysis"].  

- "Network Data Analysis" includes: ["Community Detection", "Link Prediction"].  

- "Experimental Design" includes: ["Experiment (Sampling) Plan Design", "Experiment (Sampling) Plan Evaluation"].  

- "Causal Inference" includes: ["Observational Data", "Experimental Data"].  

- "Critical Evaluation of Statistical Results" includes: ["Identification of Statistical Fallacies and Biases", "Evaluation of Reliability of Statistical Results"].  

2. Relevant variables and their roles (variables)  
Key requirements:  
    1. Variables specifically refer to the data objects collected for the research objective in the question and their statistical measures (e.g., sample size, mean, standard deviation), excluding model parameters, statistics related to specific statistical models/distributions (e.g., z-score, p-value), and statistics related to specific statistical methods (e.g., t-value, F-value).  
    2. Variable objects can be raw data columns, grouped statistics, contingency tables, sample sizes, success counts, or time variables.  
    3. In particular, if the problem to be solved in the question is of the "Mathematical Calculation" type, please treat the numerical objects such as probabilities and sample sizes actually used in the answer as variable objects for extraction.
    4. If no explicit data table is provided or `data` is empty, but symbolic variables, statistics, or logical judgment objects (e.g., `X`, `Y`, `r`, an event, a statistic) have already appeared, variables must still be extracted accordingly.  
    5. When the original data has a grouping structure, prioritize splitting the data into multiple variables according to the grouping. If each sample belongs to different groups based on different grouping methods, after splitting, additionally note in the description of these variables that they share the same samples with certain other variables but represent different groupings/features.  
    6. If the problem provides aggregated measures for multiple variables (e.g., mean, standard deviation, sample size), create a separate variable object for each variable and write these aggregated measures into the `value` field of each variable object in JSON format.  
    7. If the information is insufficient to support any variables, directly output an empty JSON: `{}`.  
    8. The output must be strictly JSON, with the top-level keys being variable IDs, and no additional text should be output.  

Field specifications:  
- Top-level key: "Variable name (extracted from the problem or an appropriately assigned variable name)".  
- `id`: Variable identifier, must exactly match the top-level key.  
- `value`: The complete value of the current variable. If it is a column from a table, an array can be used; if it is aggregated measures (including statistics, sample size, etc.), a JSON value can be used (keys are the names of the aggregated measures, and values are the corresponding values); if neither of the above forms is suitable for representation, copy and paste the original recorded form of the variable from the problem (e.g., a table recorded in TeX syntax). When there are multiple numerical values in `value`, ensure their order matches the original order in the problem.  
- `class`: Can only be one of `numerical`, `categorical`, or `others`. (Numerical type is denoted as "numerical", categorical type as "categorical", and those not belonging to the above categories as "others".)  
- `role`: Can only be one of `X`, `Y`, `XY`, or `NR`.  
  - `X`: Independent variable. Refers to a variable actively manipulated by the researcher or naturally existing and not influenced by other variables. It is the cause or condition that induces changes in other variables. The original variables used to construct the independent variable also belong to this role.  
  - `Y`: Dependent variable or explained variable. Refers to a variable whose changes are caused by changes in the independent variable. It is the outcome observed and measured by the researcher. The original variables used to construct the dependent variable also belong to this role.  
  > Please note: The roles `X` and `Y` are distinguished only when there is a clear directional relationship between variables (they always appear together).  
  - `XY`: Refers to studying the correlation between two (or more) variables without the need to distinguish causality, or when the variable plays both causal roles.  
  - `NR`: No need to specify direction. Refers to situations where it is unnecessary to distinguish between independent and dependent variables. This generally includes the following cases:  
      - Variables used solely as sample identifiers or indices, which must be included in the variable set to match samples across multiple datasets.  
      - Variables used solely to filter a subset of samples for analysis (e.g., the "year" variable when studying data from 2020) and thus must be included in the variable set.  
      - Variables involved in unsupervised methods (clustering, dimensionality reduction).  
      - Variables involved only in describing the numerical distribution of data or the stationarity of a time series.  
> Special cases for `role`:  
    1. For "Trends Over Time" problems under "Data Visualization," the variable representing the time concept must be assigned as `X`, and the variable changing over time as `Y` (even if the time variable does not appear in the variable set). For example, when studying the sales trend over different time points, the time variable is `X`, and the sales variable is `Y`.  
    2. If a variable serves both as an independent variable and is used to construct the dependent variable, its role is `X`.  
    3. If a variable serves both as a dependent variable and is used to construct the independent variable, its role is `Y`.  
- `description`: A brief description of the variable object.  

- For relatively shallow analyses of correlations between variables, "Data Visualization" methods are generally used for intuitive presentation. For deeper analysis of the direction, magnitude, and significance of correlations, building a model and interpreting the model results is generally considered.  
- Problems involving forecasting future sequences in time series should be categorized under "Continuous Value Prediction," while "Time Series Analysis" focuses on interpreting time series models.  

The output format is JSON. A complete output example is as follows:  

{
  "method": "Relationship Between Continuous Variables",
   "variables": {
    "X_height": {
      "id": "X_height",
      "value": {
        "μ": 138,
        "σ": 7
      },
      "class": "numerical",
      "role": "NR",
      "description": "Heights of 10-year-old boys, following a Normal distribution with population mean μ=138 cm and population standard deviation σ=7 cm."
    },
    "threshold": {
      "id": "threshold",
      "value": 150,
      "class": "numerical",
      "role": "NR",
      "description": "The cutoff value (150 cm) used in the answer to compute the proportion of the population below this height, directly substituted into the z-score formula z=(150−138)/7."
    }
  }
}

---

Your task is to rewrite the 'question' and 'background' fields of the original statistical problem (leaving the 'data' field unchanged), so that the resulting statistical problem presents a more complex abstraction and modelling challenge.


The requirements are as follows:

- The wording may be appropriately vague.
- Describe the problem using the business language of the relevant field; do not use statistical terminology, nor directly specify the statistical models or methods required to solve the problem.
- You may introduce some distracting information as appropriate.

You must also adhere to the following principles:

- The rewritten input can still be mapped to the formalised statistical model in the output.
- You must not alter any numerical values contained in the original problem, nor create new data without authorisation.
- You must not deviate from the direction of the original problem.
- You must not create a new problem.
- If the original question mentions tables or figures, the labels of these tables and figures must not be altered.
- Output the rewritten problem directly, without adding any prompts.

Some Examples:

1.

Input:{
  "background": "Consider a normal distribution with unknown mean $\\mu$ and unknown standard deviation $\\sigma$. Suppose we draw a random sample of size $\\mathrm{n}=16$ from this population, and the sample values are:\n$$\n\\begin{array}{l|l|l|l}\n\\hline 16.16 & 9.33 & 12.96 & 11.49 \\\\\n\\hline 12.31 & 8.93 & 6.02 & 10.66 \\\\\n\\hline 7.75 & 15.55 & 3.58 & 11.34 \\\\\n\\hline 11.38 & 6.53 & 9.75 & 9.47 \\\\\n\\hline\n\\end{array}\n$$",
  "data": null,
  "question": "What is the sample standard deviation and the critical t-value?"
}

Output:{
  "background": "Consider a normal distribution with unknown mean $\\mu$ and unknown standard deviation $\\sigma$. Suppose we draw a random sample of size $\\mathrm{n}=16$ from this population, and the sample values are:\n$$\n\\begin{array}{l|l|l|l}\n\\hline 16.16 & 9.33 & 12.96 & 11.49 \\\\\n\\hline 12.31 & 8.93 & 6.02 & 10.66 \\\\\n\\hline 7.75 & 15.55 & 3.58 & 11.34 \\\\\n\\hline 11.38 & 6.53 & 9.75 & 9.47 \\\\\n\\hline\n\\end{array}\n$$",
  "question": "What is the sample standard deviation and the critical t-value?"
}

2. 

Input:{
  "background": "The problem involves analyzing the relationship between the auction price of grandfather clocks, their age, and the number of bidders. The collector believes that the rate of increase in auction price with age is influenced by the number of bidders, leading to an interaction model. The model is fitted using 32 data points, and a portion of the Minitab printout is provided for analysis.",
  "data": "\\begin{tabular}{|l|l|l|l|l|l|}\n\\hline Table 12.1 & \\multicolumn{5}{|c|}{Auction Price Data} \\\\\n\\hline Age, $x_1$ & Number of Bidders, $\\boldsymbol{x}_{\\mathbf{2}}$ & Auction Price, $y$ & Age, $x_1$ & Number of Bidders, $x_2$ & Auction Price, $y$ \\\\\n\\hline 127 & 13 & \\$1,235 & 170 & 14 & \\$2,131 \\\\\n\\hline 115 & 12 & 1,080 & 182 & 8 & 1,550 \\\\\n\\hline 127 & 7 & 845 & 162 & 11 & 1,884 \\\\\n\\hline 150 & 9 & 1,522 & 184 & 10 & 2,041 \\\\\n\\hline 156 & 6 & 1,047 & 143 & 6 & 845 \\\\\n\\hline 182 & 11 & 1,979 & 159 & 9 & 1,483 \\\\\n\\hline 156 & 12 & 1,822 & 108 & 14 & 1,055 \\\\\n\\hline 132 & 10 & 1,253 & 175 & 8 & 1,545 \\\\\n\\hline 137 & 9 & 1,297 & 108 & 6 & 729 \\\\\n\\hline 113 & 9 & 946 & 179 & 9 & 1,792 \\\\\n\\hline 137 & 15 & 1,713 & 111 & 15 & 1,175 \\\\\n\\hline 117 & 11 & 1,024 & 187 & 8 & 1,593 \\\\\n\\hline 137 & 8 & 1,147 & 111 & 7 & 785 \\\\\n\\hline 153 & 6 & 1,092 & 115 & 7 & 744 \\\\\n\\hline 117 & 13 & 1,152 & 194 & 5 & 1,356 \\\\\n\\hline 126 & 10 & 1,336 & 168 & 7 & 1,262 \\\\\n\\hline\n\\end{tabular}",
  "question": "Estimate the change in auction price of a 150-year-old grandfather clock, $y$, for each additional bidder."
}

Output:{
  "background": "A specialty antiques house is preparing client guidance ahead of its next grandfather clock sale cycle and is revisiting 32 prior transactions listed in Table 12.1. Commercial staff have been debating whether buyer traffic should be discussed in a uniform way across all pieces, since the same increase in live interest may translate differently for clocks from different eras. In practice, consignors often ask why two lots with similar turnout did not finish with comparable hammer results, and specialists point to a mix of vintage, room energy, presentation, and other lot-specific details. For this review, management wants the pricing team to focus on the historical records already assembled and translate the interplay between a clock’s age and bidder participation into a simple talking point that can be used in valuation conversations.",
  "question": "Using the information available from Table 12.1 and the internal summary, if a grandfather clock is 150 years old, how much additional dollar value in auction price, $y$, should the house attribute to bringing in one more bidder?"
}

As you only need to change the 'background' and 'question' fields in the input, please output the data in the following JSON format:

{"background":"xxx","question":"xxx"}
'''


prompt_think ='''
You are a statistician. You currently have a dataset designed to evaluate the abstraction and modelling of statistical problems; each sample contains an input (the original statistical problem) and an output (an abstract statistical model derived from the original problem).

---

The input format is:

{
    "background": "Relevant description of the problem context (which may also contain some data)",
    "data": "The data used, presented as a table in LaTeX code",
    "question": "The core problem"
}

The abstracted statistical model includes the following four parts:  
1. Method category (method), which is the category of the statistical model used and must strictly come from the following framework (the result should be from the content within []):  

- "Data Preprocessing" includes: ["Missing Value Handling", "Outlier Handling", "Standardization", "Binning", "Transformation"].  

- "Mathematical Calculation" includes: ["Probability Space Related (e.g., number of states)", "Event Probability and Independence", "Expectation", "Minimum Sample Size Required to Achieve a Specified Probability", "Distribution Derivation", "Other"].  

- "Numerical Computation" includes: ["Obtaining Model Parameter Estimates", "Sampling from a Specified Distribution"].  

- "Descriptive Statistics" includes: ["Measures of Central Tendency", "Measures of Dispersion", "Measures of Distribution Range", "Measures of Frequency and Proportion", "Quantiles/Percentiles", "Network Graph Indicators", "Analysis and Comparison of Statistical Properties", "Other (e.g., reliability)"].  

- The "Data Distribution Modelling" section includes: ["Model Building", "MLE", "Bayesian"].

- "Data Visualization" includes: ["Distribution of Discrete Variables", "Distribution of Continuous Variables", "Relationship Between Discrete and Continuous Variables", "Relationship Between Continuous Variables", "Relationship Between Discrete Variables", "Comprehensive Comparison of Multiple Variables", "Trends Over Time", "Spatial and Geographic Visualization", "Text and Symbolic Visualization", "Stem-and-Leaf Plot", "Other Statistical Graphics"].  

- "Association Analysis" includes: ["Correlation Coefficient (One-dimensional)", "CCA (Multidimensional)", "Contingency Table"].  

- "Clustering" includes only: ["Clustering"].  

- "Dimensionality Reduction" includes only: ["Dimensionality Reduction"].  

- "Hypothesis Testing and Interval Estimation" includes: ["Independence Test", "Mean Test", "Variance Test", "ANOVA", "Distribution Test", "Proportion Test", "Likelihood Ratio Test", "Sequential Test", "Randomness", "Regression Model Parameter Test", "Analysis of Test Properties"]. (Note: Since hypothesis testing and interval estimation are two sides of the same coin, although the secondary categories below are mostly named with "test", they also include corresponding interval estimation methods.)  

- "Model Comparison (Variable Selection)" includes: ["Criterion-Based Comparison (AIC, BIC, etc.)", "Cross-Validation", "Likelihood Ratio Test", "ROC Curve (AUC), Coverage-Capture Rate Curve", "Identification of Important Variables"].  

- "Model Diagnosis" includes: ["Residual Analysis", "Goodness-of-Fit Assessment"].  

- "Model Interpretation" includes: ["Interpretation of Regression Coefficient Significance and Direction", "Interpretation of Regression Effect Size", "Interpretation of Factors Influencing Classification or Occurrence Probability", "Interpretation of Mechanisms Influencing Ordered Outcomes", "Interpretation of Variable Importance Ranking", "Interpretation of Group Heterogeneity"].  

- "Classification and Prediction" includes: ["Continuous Value Prediction", "Categorical Variable Classification", "Multi-class Classification of Ordered Variables", "Quantile Prediction", "Survival Analysis"].  

- "Time Series Analysis" includes: ["Lag Correlation Analysis", "Stationarity Analysis", "Seasonality Analysis", "Deterministic Factor Decomposition", "Volatility Analysis"].  

- "Text Data Analysis" includes: ["Tokenization", "Word Frequency Statistics", "Topic Modeling", "Sentiment Analysis"].  

- "Network Data Analysis" includes: ["Community Detection", "Link Prediction"].  

- "Experimental Design" includes: ["Experiment (Sampling) Plan Design", "Experiment (Sampling) Plan Evaluation"].  

- "Causal Inference" includes: ["Observational Data", "Experimental Data"].  

- "Critical Evaluation of Statistical Results" includes: ["Identification of Statistical Fallacies and Biases", "Evaluation of Reliability of Statistical Results"].  

2. Relevant variables and their roles (variables)  
Key requirements:  
    1. Variables specifically refer to the data objects collected for the research objective in the question and their statistical measures (e.g., sample size, mean, standard deviation), excluding model parameters, statistics related to specific statistical models/distributions (e.g., z-score, p-value), and statistics related to specific statistical methods (e.g., t-value, F-value).  
    2. Variable objects can be raw data columns, grouped statistics, contingency tables, sample sizes, success counts, or time variables.  
    3. In particular, if the problem to be solved in the question is of the "Mathematical Calculation" type, please treat the numerical objects such as probabilities and sample sizes actually used in the answer as variable objects for extraction.
    4. If no explicit data table is provided or `data` is empty, but symbolic variables, statistics, or logical judgment objects (e.g., `X`, `Y`, `r`, an event, a statistic) have already appeared, variables must still be extracted accordingly.  
    5. When the original data has a grouping structure, prioritize splitting the data into multiple variables according to the grouping. If each sample belongs to different groups based on different grouping methods, after splitting, additionally note in the description of these variables that they share the same samples with certain other variables but represent different groupings/features.  
    6. If the problem provides aggregated measures for multiple variables (e.g., mean, standard deviation, sample size), create a separate variable object for each variable and write these aggregated measures into the `value` field of each variable object in JSON format.  
    7. If the information is insufficient to support any variables, directly output an empty JSON: `{}`.  
    8. The output must be strictly JSON, with the top-level keys being variable IDs, and no additional text should be output.  

Field specifications:  
- Top-level key: "Variable name (extracted from the problem or an appropriately assigned variable name)".  
- `id`: Variable identifier, must exactly match the top-level key.  
- `value`: The complete value of the current variable. If it is a column from a table, an array can be used; if it is aggregated measures (including statistics, sample size, etc.), a JSON value can be used (keys are the names of the aggregated measures, and values are the corresponding values); if neither of the above forms is suitable for representation, copy and paste the original recorded form of the variable from the problem (e.g., a table recorded in TeX syntax). When there are multiple numerical values in `value`, ensure their order matches the original order in the problem.  
- `class`: Can only be one of `numerical`, `categorical`, or `others`. (Numerical type is denoted as "numerical", categorical type as "categorical", and those not belonging to the above categories as "others".)  
- `role`: Can only be one of `X`, `Y`, `XY`, or `NR`.  
  - `X`: Independent variable. Refers to a variable actively manipulated by the researcher or naturally existing and not influenced by other variables. It is the cause or condition that induces changes in other variables. The original variables used to construct the independent variable also belong to this role.  
  - `Y`: Dependent variable or explained variable. Refers to a variable whose changes are caused by changes in the independent variable. It is the outcome observed and measured by the researcher. The original variables used to construct the dependent variable also belong to this role.  
  > Please note: The roles `X` and `Y` are distinguished only when there is a clear directional relationship between variables (they always appear together).  
  - `XY`: Refers to studying the correlation between two (or more) variables without the need to distinguish causality, or when the variable plays both causal roles.  
  - `NR`: No need to specify direction. Refers to situations where it is unnecessary to distinguish between independent and dependent variables. This generally includes the following cases:  
      - Variables used solely as sample identifiers or indices, which must be included in the variable set to match samples across multiple datasets.  
      - Variables used solely to filter a subset of samples for analysis (e.g., the "year" variable when studying data from 2020) and thus must be included in the variable set.  
      - Variables involved in unsupervised methods (clustering, dimensionality reduction).  
      - Variables involved only in describing the numerical distribution of data or the stationarity of a time series.  
> Special cases for `role`:  
    1. For "Trends Over Time" problems under "Data Visualization," the variable representing the time concept must be assigned as `X`, and the variable changing over time as `Y` (even if the time variable does not appear in the variable set). For example, when studying the sales trend over different time points, the time variable is `X`, and the sales variable is `Y`.  
    2. If a variable serves both as an independent variable and is used to construct the dependent variable, its role is `X`.  
    3. If a variable serves both as a dependent variable and is used to construct the independent variable, its role is `Y`.  
- `description`: A brief description of the variable object.  

- For relatively shallow analyses of correlations between variables, "Data Visualization" methods are generally used for intuitive presentation. For deeper analysis of the direction, magnitude, and significance of correlations, building a model and interpreting the model results is generally considered.  
- Problems involving forecasting future sequences in time series should be categorized under "Continuous Value Prediction," while "Time Series Analysis" focuses on interpreting time series models.  

The output format is JSON. A complete output example is as follows:  

{
  "method": "Relationship Between Continuous Variables",
   "variables": {
    "X_height": {
      "id": "X_height",
      "value": {
        "μ": 138,
        "σ": 7
      },
      "class": "numerical",
      "role": "NR",
      "description": "Heights of 10-year-old boys, following a Normal distribution with population mean μ=138 cm and population standard deviation σ=7 cm."
    },
    "threshold": {
      "id": "threshold",
      "value": 150,
      "class": "numerical",
      "role": "NR",
      "description": "The cutoff value (150 cm) used in the answer to compute the proportion of the population below this height, directly substituted into the z-score formula z=(150−138)/7."
    }
  }
}

---

Your task is to analyse, based on a specific sample from this dataset, the rationale for why the output (an abstract statistical model derived from the original problem) corresponds to the formalised statistical model of the input (the original statistical problem). Please output the result directly, without including any additional prompts.


'''

quality_check_prompt = '''
You are an expert evaluator of problem reformulation. Each sample contains an input (the original statistical problem) and an output (an abstract statistical model derived from the original problem).

The input format is:

{
    "background": "Relevant description of the problem context (which may also contain some data)",
    "data": "The data used, presented as a table in LaTeX code",
    "question": "The core problem"
}

The abstracted statistical model includes the following four parts:  
1. Method category (method), which is the category of the statistical model used and must strictly come from the following framework (the result should be from the content within []):  

- "Data Preprocessing" includes: ["Missing Value Handling", "Outlier Handling", "Standardization", "Binning", "Transformation"].  

- "Mathematical Calculation" includes: ["Probability Space Related (e.g., number of states)", "Event Probability and Independence", "Expectation", "Minimum Sample Size Required to Achieve a Specified Probability", "Distribution Derivation", "Other"].  

- "Numerical Computation" includes: ["Obtaining Model Parameter Estimates", "Sampling from a Specified Distribution"].  

- "Descriptive Statistics" includes: ["Measures of Central Tendency", "Measures of Dispersion", "Measures of Distribution Range", "Measures of Frequency and Proportion", "Quantiles/Percentiles", "Network Graph Indicators", "Analysis and Comparison of Statistical Properties", "Other (e.g., reliability)"].  

- The "Data Distribution Modelling" section includes: ["Model Building", "MLE", "Bayesian"].

- "Data Visualization" includes: ["Distribution of Discrete Variables", "Distribution of Continuous Variables", "Relationship Between Discrete and Continuous Variables", "Relationship Between Continuous Variables", "Relationship Between Discrete Variables", "Comprehensive Comparison of Multiple Variables", "Trends Over Time", "Spatial and Geographic Visualization", "Text and Symbolic Visualization", "Stem-and-Leaf Plot", "Other Statistical Graphics"].  

- "Association Analysis" includes: ["Correlation Coefficient (One-dimensional)", "CCA (Multidimensional)", "Contingency Table"].  

- "Clustering" includes only: ["Clustering"].  

- "Dimensionality Reduction" includes only: ["Dimensionality Reduction"].  

- "Hypothesis Testing and Interval Estimation" includes: ["Independence Test", "Mean Test", "Variance Test", "ANOVA", "Distribution Test", "Proportion Test", "Likelihood Ratio Test", "Sequential Test", "Randomness", "Regression Model Parameter Test", "Analysis of Test Properties"]. (Note: Since hypothesis testing and interval estimation are two sides of the same coin, although the secondary categories below are mostly named with "test", they also include corresponding interval estimation methods.)  

- "Model Comparison (Variable Selection)" includes: ["Criterion-Based Comparison (AIC, BIC, etc.)", "Cross-Validation", "Likelihood Ratio Test", "ROC Curve (AUC), Coverage-Capture Rate Curve", "Identification of Important Variables"].  

- "Model Diagnosis" includes: ["Residual Analysis", "Goodness-of-Fit Assessment"].  

- "Model Interpretation" includes: ["Interpretation of Regression Coefficient Significance and Direction", "Interpretation of Regression Effect Size", "Interpretation of Factors Influencing Classification or Occurrence Probability", "Interpretation of Mechanisms Influencing Ordered Outcomes", "Interpretation of Variable Importance Ranking", "Interpretation of Group Heterogeneity"].  

- "Classification and Prediction" includes: ["Continuous Value Prediction", "Categorical Variable Classification", "Multi-class Classification of Ordered Variables", "Quantile Prediction", "Survival Analysis"].  

- "Time Series Analysis" includes: ["Lag Correlation Analysis", "Stationarity Analysis", "Seasonality Analysis", "Deterministic Factor Decomposition", "Volatility Analysis"].  

- "Text Data Analysis" includes: ["Tokenization", "Word Frequency Statistics", "Topic Modeling", "Sentiment Analysis"].  

- "Network Data Analysis" includes: ["Community Detection", "Link Prediction"].  

- "Experimental Design" includes: ["Experiment (Sampling) Plan Design", "Experiment (Sampling) Plan Evaluation"].  

- "Causal Inference" includes: ["Observational Data", "Experimental Data"].  

- "Critical Evaluation of Statistical Results" includes: ["Identification of Statistical Fallacies and Biases", "Evaluation of Reliability of Statistical Results"].  

2. Relevant variables and their roles (variables)  
Key requirements:  
    1. Variables specifically refer to the data objects collected for the research objective in the question and their statistical measures (e.g., sample size, mean, standard deviation), excluding model parameters, statistics related to specific statistical models/distributions (e.g., z-score, p-value), and statistics related to specific statistical methods (e.g., t-value, F-value).  
    2. Variable objects can be raw data columns, grouped statistics, contingency tables, sample sizes, success counts, or time variables.  
    3. In particular, if the problem to be solved in the question is of the "Mathematical Calculation" type, please treat the numerical objects such as probabilities and sample sizes actually used in the answer as variable objects for extraction.
    4. If no explicit data table is provided or `data` is empty, but symbolic variables, statistics, or logical judgment objects (e.g., `X`, `Y`, `r`, an event, a statistic) have already appeared, variables must still be extracted accordingly.  
    5. When the original data has a grouping structure, prioritize splitting the data into multiple variables according to the grouping. If each sample belongs to different groups based on different grouping methods, after splitting, additionally note in the description of these variables that they share the same samples with certain other variables but represent different groupings/features.  
    6. If the problem provides aggregated measures for multiple variables (e.g., mean, standard deviation, sample size), create a separate variable object for each variable and write these aggregated measures into the `value` field of each variable object in JSON format.  
    7. If the information is insufficient to support any variables, directly output an empty JSON: `{}`.  
    8. The output must be strictly JSON, with the top-level keys being variable IDs, and no additional text should be output.  

Field specifications:  
- Top-level key: "Variable name (extracted from the problem or an appropriately assigned variable name)".  
- `id`: Variable identifier, must exactly match the top-level key.  
- `value`: The complete value of the current variable. If it is a column from a table, an array can be used; if it is aggregated measures (including statistics, sample size, etc.), a JSON value can be used (keys are the names of the aggregated measures, and values are the corresponding values); if neither of the above forms is suitable for representation, copy and paste the original recorded form of the variable from the problem (e.g., a table recorded in TeX syntax). When there are multiple numerical values in `value`, ensure their order matches the original order in the problem.  
- `class`: Can only be one of `numerical`, `categorical`, or `others`. (Numerical type is denoted as "numerical", categorical type as "categorical", and those not belonging to the above categories as "others".)  
- `role`: Can only be one of `X`, `Y`, `XY`, or `NR`.  
  - `X`: Independent variable. Refers to a variable actively manipulated by the researcher or naturally existing and not influenced by other variables. It is the cause or condition that induces changes in other variables. The original variables used to construct the independent variable also belong to this role.  
  - `Y`: Dependent variable or explained variable. Refers to a variable whose changes are caused by changes in the independent variable. It is the outcome observed and measured by the researcher. The original variables used to construct the dependent variable also belong to this role.  
  > Please note: The roles `X` and `Y` are distinguished only when there is a clear directional relationship between variables (they always appear together).  
  - `XY`: Refers to studying the correlation between two (or more) variables without the need to distinguish causality, or when the variable plays both causal roles.  
  - `NR`: No need to specify direction. Refers to situations where it is unnecessary to distinguish between independent and dependent variables. This generally includes the following cases:  
      - Variables used solely as sample identifiers or indices, which must be included in the variable set to match samples across multiple datasets.  
      - Variables used solely to filter a subset of samples for analysis (e.g., the "year" variable when studying data from 2020) and thus must be included in the variable set.  
      - Variables involved in unsupervised methods (clustering, dimensionality reduction).  
      - Variables involved only in describing the numerical distribution of data or the stationarity of a time series.  
> Special cases for `role`:  
    1. For "Trends Over Time" problems under "Data Visualization," the variable representing the time concept must be assigned as `X`, and the variable changing over time as `Y` (even if the time variable does not appear in the variable set). For example, when studying the sales trend over different time points, the time variable is `X`, and the sales variable is `Y`.  
    2. If a variable serves both as an independent variable and is used to construct the dependent variable, its role is `X`.  
    3. If a variable serves both as a dependent variable and is used to construct the independent variable, its role is `Y`.  
- `description`: A brief description of the variable object.  

- For relatively shallow analyses of correlations between variables, "Data Visualization" methods are generally used for intuitive presentation. For deeper analysis of the direction, magnitude, and significance of correlations, building a model and interpreting the model results is generally considered.  
- Problems involving forecasting future sequences in time series should be categorized under "Continuous Value Prediction," while "Time Series Analysis" focuses on interpreting time series models.  

The output format is JSON. A complete output example is as follows:  

{
  "method": "Relationship Between Continuous Variables",
   "variables": {
    "X_height": {
      "id": "X_height",
      "value": {
        "μ": 138,
        "σ": 7
      },
      "class": "numerical",
      "role": "NR",
      "description": "Heights of 10-year-old boys, following a Normal distribution with population mean μ=138 cm and population standard deviation σ=7 cm."
    },
    "threshold": {
      "id": "threshold",
      "value": 150,
      "class": "numerical",
      "role": "NR",
      "description": "The cutoff value (150 cm) used in the answer to compute the proportion of the population below this height, directly substituted into the z-score formula z=(150−138)/7."
    }
  }
}

We have rewritten the 'background' and 'question' fields in the original query to produce the result (Rewritten problem). Your task is to:

1. check whether a rewritten problem meets the following standards:

- The numerical values in the original problem must not be altered, nor new data created without authorization.
- The direction of the original problem must not be deviated from.
- A new problem must not be created.
- If the original question mentions tables or figures, the labels of these tables and figures must not be altered.

Note: 

- It is acceptable for the reworded question to contain some vague language or irrelevant information, provided that this does not alter the meaning of the original question.
- The question must not directly specify the name of the statistical method required to solve it.


2. determine whether the rewritten problem matches the given formal statistical model

---

Please evaluate the rewritten problem against the original problem and provide:
1. A boolean result (true/false) indicating whether the rewrite meets all standards
2. Specific feedback on any issues found

Original input-output:
{original_input_output}

The reason for deriving this statistical model from the original problem is
{reason}

Rewritten problem:
{rewritten}

Output format:
{{
  "pass": true/false,
  "feedback": "Your feedback here"
}}
'''