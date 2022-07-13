from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest
import woodwork as ww

from evalml.automl.engine.cf_engine import CFClient, CFComputation, CFEngine
from evalml.automl.engine.engine_base import (
    JobLogger,
    evaluate_pipeline,
    train_pipeline,
)
from evalml.automl.engine.sequential_engine import SequentialEngine
from evalml.automl.utils import AutoMLConfig
from evalml.pipelines import BinaryClassificationPipeline
from evalml.pipelines.pipeline_base import PipelineBase
from evalml.tests.automl_tests.dask_test_utils import (
    DaskPipelineSlow,
    DaskSchemaCheckPipeline,
    automl_data,
)


@pytest.fixture(scope="module")
def process_pool():
    process_pool = ProcessPoolExecutor()
    yield process_pool
    process_pool.shutdown()


@pytest.fixture(scope="module")
def thread_pool():
    thread_pool = ThreadPoolExecutor()
    yield thread_pool
    thread_pool.shutdown()


def get_pool(pool_type, thread_pool, process_pool):
    if pool_type == "threads":
        return thread_pool
    elif pool_type == "processes":
        return process_pool


def test_init(process_pool):
    with CFClient(process_pool) as client:
        engine = CFEngine(client=client)
        assert engine.client == client

        with pytest.raises(
            TypeError,
            match="Expected evalml.automl.engine.cf_engine.CFClient, received",
        ):
            CFEngine(client="CFClient")


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_training_job_single(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that training a single pipeline using the parallel engine produces the
    same results as simply running the train_pipeline function."""
    X, y = X_y_binary_cls
    pool = get_pool(pool_type, thread_pool, process_pool)
    with CFClient(pool) as client:
        engine = CFEngine(client=client)
        pipeline = BinaryClassificationPipeline(
            component_graph=["Logistic Regression Classifier"],
            parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
        )

        # Verify that engine fits a pipeline
        pipeline_future = engine.submit_training_job(
            X=X,
            y=y,
            automl_config=automl_data,
            pipeline=pipeline,
        )
        dask_pipeline_fitted = pipeline_future.get_result()[0]
        assert dask_pipeline_fitted._is_fitted

        # Verify parallelization has no effect on output of function
        original_pipeline_fitted = train_pipeline(
            pipeline,
            X,
            y,
            automl_config=automl_data,
        )[0]
        assert dask_pipeline_fitted == original_pipeline_fitted
        pd.testing.assert_series_equal(
            dask_pipeline_fitted.predict(X),
            original_pipeline_fitted.predict(X),
        )


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_training_jobs_multiple(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that training multiple pipelines using the parallel engine produces the
    same results as the sequential engine."""
    X, y = X_y_binary_cls
    pool = get_pool(pool_type, thread_pool, process_pool)
    with CFClient(pool) as client:
        pipelines = [
            BinaryClassificationPipeline(
                component_graph=["Logistic Regression Classifier"],
                parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
            ),
            BinaryClassificationPipeline(component_graph=["Baseline Classifier"]),
            BinaryClassificationPipeline(component_graph=["SVM Classifier"]),
        ]

        def fit_pipelines(pipelines, engine):
            futures = []
            for pipeline in pipelines:
                futures.append(
                    engine.submit_training_job(
                        X=X,
                        y=y,
                        automl_config=automl_data,
                        pipeline=pipeline,
                    ),
                )
            results = [f.get_result()[0] for f in futures]
            return results

        # Verify all pipelines are trained and fitted.
        seq_pipelines = fit_pipelines(pipelines, SequentialEngine())
        for pipeline in seq_pipelines:
            assert pipeline._is_fitted

        # Verify all pipelines are trained and fitted.
        par_pipelines = fit_pipelines(pipelines, CFEngine(client=client))
        for pipeline in par_pipelines:
            assert pipeline._is_fitted

        # Ensure sequential and parallel pipelines are equivalent
        assert len(par_pipelines) == len(seq_pipelines)
        for par_pipeline in par_pipelines:
            assert par_pipeline in seq_pipelines


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_evaluate_job_single(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that evaluating a single pipeline using the parallel engine produces the
    same results as simply running the evaluate_pipeline function."""
    X, y = X_y_binary_cls
    X.ww.init()
    y = ww.init_series(y)
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:

        pipeline = BinaryClassificationPipeline(
            component_graph=["Logistic Regression Classifier"],
            parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
        )

        engine = CFEngine(client=client)

        # Verify that engine evaluates a pipeline
        pipeline_future = engine.submit_evaluation_job(
            X=X,
            y=y,
            automl_config=automl_data,
            pipeline=pipeline,
        )
        assert isinstance(pipeline_future, CFComputation)

        par_eval_results = pipeline_future.get_result()

        original_eval_results = evaluate_pipeline(
            pipeline,
            automl_config=automl_data,
            X=X,
            y=y,
            logger=JobLogger(),
        )

        # Ensure we get back the same output as the parallelized function.
        assert len(par_eval_results) == 4

        par_scores = par_eval_results.get("scores")
        original_eval_scores = original_eval_results.get("scores")

        # Compare cross validation information except training time.
        assert par_scores["cv_data"] == original_eval_scores["cv_data"]
        assert all(par_scores["cv_scores"] == original_eval_scores["cv_scores"])
        assert par_scores["cv_score_mean"] == par_scores["cv_score_mean"]

        # Make sure the resulting pipelines are the same.
        assert isinstance(par_eval_results.get("pipeline"), PipelineBase)
        assert par_eval_results.get("pipeline") == original_eval_results.get("pipeline")

        # Make sure a properly filled logger comes back.
        assert isinstance(par_eval_results.get("logger"), JobLogger)
        assert (
            par_eval_results.get("logger").logs
            == original_eval_results.get("logger").logs
        )


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_evaluate_jobs_multiple(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that evaluating multiple pipelines using the parallel engine produces the
    same results as the sequential engine."""
    X, y = X_y_binary_cls
    X.ww.init()
    y = ww.init_series(y)
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:

        pipelines = [
            BinaryClassificationPipeline(
                component_graph=["Logistic Regression Classifier"],
                parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
            ),
            BinaryClassificationPipeline(component_graph=["Baseline Classifier"]),
            BinaryClassificationPipeline(component_graph=["SVM Classifier"]),
        ]

        def eval_pipelines(pipelines, engine):
            futures = []
            for pipeline in pipelines:
                futures.append(
                    engine.submit_evaluation_job(
                        X=X,
                        y=y,
                        automl_config=automl_data,
                        pipeline=pipeline,
                    ),
                )
            results = [f.get_result() for f in futures]
            return results

        par_eval_results = eval_pipelines(pipelines, CFEngine(client=client))
        par_dicts = [s.get("scores") for s in par_eval_results]
        par_scores = [s["cv_data"][0]["mean_cv_score"] for s in par_dicts]
        par_pipelines = [s.get("pipeline") for s in par_eval_results]

        seq_eval_results = eval_pipelines(pipelines, SequentialEngine())
        seq_dicts = [s.get("scores") for s in seq_eval_results]
        seq_scores = [s["cv_data"][0]["mean_cv_score"] for s in seq_dicts]
        seq_pipelines = [s.get("pipeline") for s in seq_eval_results]

        # Ensure all pipelines are fitted.
        assert all([s._is_fitted for s in par_pipelines])

        # Ensure the scores in parallel and sequence are same
        assert not any([np.isnan(s) for s in par_scores])
        assert not any([np.isnan(s) for s in seq_scores])
        np.testing.assert_allclose(par_scores, seq_scores, rtol=1e-10)

        # Ensure the parallel and sequence pipelines match
        assert len(par_pipelines) == len(seq_pipelines)
        for par_pipeline in par_pipelines:
            assert par_pipeline in seq_pipelines


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_scoring_job_single(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that scoring a single pipeline using the parallel engine produces the
    same results as simply running the score_pipeline function."""
    X, y = X_y_binary_cls
    X.ww.init()
    y = ww.init_series(y)
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:

        pipeline = BinaryClassificationPipeline(
            component_graph=["Logistic Regression Classifier"],
            parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
        )
        engine = CFEngine(client=client)
        objectives = [automl_data.objective]

        pipeline_future = engine.submit_training_job(
            X=X,
            y=y,
            automl_config=automl_data,
            pipeline=pipeline,
        )
        pipeline = pipeline_future.get_result()[0]
        pipeline_score_future = engine.submit_scoring_job(
            X=X,
            y=y,
            automl_config=automl_data,
            pipeline=pipeline,
            objectives=objectives,
        )
        assert isinstance(pipeline_score_future, CFComputation)
        pipeline_score = pipeline_score_future.get_result()

        original_pipeline_score = pipeline.score(X=X, y=y, objectives=objectives)

        assert not np.isnan(pipeline_score["Log Loss Binary"])
        assert pipeline_score == original_pipeline_score


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_submit_scoring_jobs_multiple(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    """Test that scoring multiple pipelines using the parallel engine produces the
    same results as the sequential engine."""
    X, y = X_y_binary_cls
    X.ww.init()
    y = ww.init_series(y)
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:

        pipelines = [
            BinaryClassificationPipeline(
                component_graph=["Logistic Regression Classifier"],
                parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
            ),
            BinaryClassificationPipeline(component_graph=["Baseline Classifier"]),
            BinaryClassificationPipeline(component_graph=["SVM Classifier"]),
        ]

        def score_pipelines(pipelines, engine):
            futures = []
            for pipeline in pipelines:
                futures.append(
                    engine.submit_training_job(
                        X=X,
                        y=y,
                        automl_config=automl_data,
                        pipeline=pipeline,
                    ),
                )
            pipelines = [f.get_result()[0] for f in futures]
            futures = []
            for pipeline in pipelines:
                futures.append(
                    engine.submit_scoring_job(
                        X=X,
                        y=y,
                        automl_config=automl_data,
                        pipeline=pipeline,
                        objectives=[automl_data.objective],
                    ),
                )
            results = [f.get_result() for f in futures]
            return results

        par_eval_results = score_pipelines(pipelines, CFEngine(client=client))
        par_scores = [s["Log Loss Binary"] for s in par_eval_results]

        seq_eval_results = score_pipelines(pipelines, SequentialEngine())
        seq_scores = [s["Log Loss Binary"] for s in seq_eval_results]

        # Check there are the proper number of pipelines and all their scores are same.
        assert len(par_eval_results) == len(pipelines)
        assert not any([np.isnan(s) for s in par_scores])
        assert not any([np.isnan(s) for s in seq_scores])
        np.testing.assert_allclose(par_scores, seq_scores, rtol=1e-10)


@pytest.mark.parametrize("pool_type", ["threads"])
def test_cancel_job(X_y_binary_cls, pool_type, thread_pool, process_pool):
    """Test that training a single pipeline using the parallel engine produces the
    same results as simply running the train_pipeline function."""
    X, y = X_y_binary_cls
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:
        engine = CFEngine(client=client)
        pipeline = DaskPipelineSlow({"Logistic Regression Classifier": {"n_jobs": 1}})

        # Verify that engine fits a pipeline
        pipeline_future = engine.submit_training_job(
            X=X,
            y=y,
            automl_config=automl_data,
            pipeline=pipeline,
        )
        pipeline_future.cancel()
        assert pipeline_future.is_cancelled


@pytest.mark.parametrize("pool_type", ["threads", "processes"])
def test_cfengine_sends_woodwork_schema(
    X_y_binary_cls,
    pool_type,
    thread_pool,
    process_pool,
):
    X, y = X_y_binary_cls
    pool = get_pool(pool_type, thread_pool, process_pool)

    with CFClient(pool) as client:
        engine = CFEngine(client=client)

        X.ww.init(
            logical_types={0: "Categorical"},
            semantic_tags={0: ["my cool feature"]},
        )
        y = ww.init_series(y)

        new_config = AutoMLConfig(
            data_splitter=automl_data.data_splitter,
            problem_type=automl_data.problem_type,
            objective=automl_data.objective,
            alternate_thresholding_objective=automl_data.alternate_thresholding_objective,
            additional_objectives=automl_data.additional_objectives,
            optimize_thresholds=automl_data.optimize_thresholds,
            error_callback=automl_data.error_callback,
            random_seed=automl_data.random_seed,
            X_schema=X.ww.schema,
            y_schema=y.ww.schema,
        )

        # TestSchemaCheckPipeline will verify that the schema is preserved by the time we call
        # pipeline.fit and pipeline.score
        pipeline = DaskSchemaCheckPipeline(
            component_graph=["One Hot Encoder", "Logistic Regression Classifier"],
            parameters={"Logistic Regression Classifier": {"n_jobs": 1}},
            X_schema_to_check=X.ww.schema,
            y_schema_to_check=y.ww.schema,
        )

        future = engine.submit_training_job(
            X=X,
            y=y,
            automl_config=new_config,
            pipeline=pipeline,
        )
        fitted_pipeline = future.get_result()[0]

        future = engine.submit_scoring_job(
            X=X,
            y=y,
            automl_config=new_config,
            pipeline=fitted_pipeline,
            objectives=["F1"],
        )
        _ = future.get_result()

        future = engine.submit_evaluation_job(new_config, pipeline, X, y)
        future.get_result()


def test_cfengine_convenience():
    """The purpose of this test is to ensure that a CFEngine initialized without an
    explicit client self-initializes a threaded CFClient."""

    cf_engine = CFEngine()
    assert isinstance(cf_engine.client, CFClient)
    assert isinstance(cf_engine.client.pool, ThreadPoolExecutor)

    cf_engine = CFEngine(client=None)
    assert isinstance(cf_engine.client, CFClient)
    assert isinstance(cf_engine.client.pool, ThreadPoolExecutor)

    cf_engine = CFEngine(client=CFClient(ProcessPoolExecutor()))
    assert isinstance(cf_engine.client, CFClient)
    assert isinstance(cf_engine.client.pool, ProcessPoolExecutor)

    with pytest.raises(
        TypeError,
        match="Expected evalml.automl.engine.cf_engine.CFClient, received",
    ):
        cf_engine = CFEngine(client="Processes!")


@pytest.mark.parametrize("pool_class", [ThreadPoolExecutor, ProcessPoolExecutor])
def test_automl_closes_engines(pool_class, X_y_binary_cls):
    pool_instance = pool_class()
    cf_engine = CFEngine(CFClient(pool_instance))
    cf_engine.close()
    assert cf_engine.is_closed
