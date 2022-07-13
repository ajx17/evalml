"""EvalML component classes."""
from evalml.pipelines.components.component_base import ComponentBase, ComponentBaseMeta
from evalml.pipelines.components.estimators import (
    Estimator,
    LinearRegressor,
    LightGBMClassifier,
    LightGBMRegressor,
    LogisticRegressionClassifier,
    RandomForestClassifier,
    RandomForestRegressor,
    XGBoostClassifier,
    CatBoostClassifier,
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    CatBoostRegressor,
    XGBoostRegressor,
    ElasticNetClassifier,
    ElasticNetRegressor,
    BaselineClassifier,
    BaselineRegressor,
    DecisionTreeClassifier,
    DecisionTreeRegressor,
    TimeSeriesBaselineEstimator,
    KNeighborsClassifier,
    ProphetRegressor,
    SVMClassifier,
    SVMRegressor,
    ExponentialSmoothingRegressor,
    ARIMARegressor,
    VowpalWabbitBinaryClassifier,
    VowpalWabbitMulticlassClassifier,
    VowpalWabbitRegressor,
)
from evalml.pipelines.components.transformers import (
    Transformer,
    OneHotEncoder,
    TargetEncoder,
    RFClassifierSelectFromModel,
    RFRegressorSelectFromModel,
    PerColumnImputer,
    TimeSeriesFeaturizer,
    SimpleImputer,
    Imputer,
    TimeSeriesImputer,
    StandardScaler,
    FeatureSelector,
    DropColumns,
    DropNullColumns,
    DateTimeFeaturizer,
    SelectColumns,
    SelectByType,
    NaturalLanguageFeaturizer,
    LinearDiscriminantAnalysis,
    LSA,
    PCA,
    DFSTransformer,
    Undersampler,
    TargetImputer,
    PolynomialDetrender,
    Oversampler,
    LogTransformer,
    EmailFeaturizer,
    URLFeaturizer,
    DropRowsTransformer,
    LabelEncoder,
    ReplaceNullableTypes,
    DropNaNRowsTransformer,
    TimeSeriesRegularizer,
)
from evalml.pipelines.components.ensemble import (
    StackedEnsembleClassifier,
    StackedEnsembleRegressor,
)
