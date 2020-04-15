from evalml.pipelines import MulticlassClassificationPipeline


class RFMulticlassClassificationPipeline(MulticlassClassificationPipeline):
    """Random Forest Pipeline for multiclass classification"""
    custom_name = "Random Forest Multi-class Classification Pipeline"
    component_graph = ['One Hot Encoder', 'Simple Imputer', 'RF Classifier Select From Model', 'Random Forest Classifier']