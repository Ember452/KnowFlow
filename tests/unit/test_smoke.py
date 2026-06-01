"""冒烟测试 - 验证包可导入与基本配置加载。"""


def test_knowflow_importable() -> None:
    """knowflow 包应可正常导入且暴露版本号。"""
    import knowflow

    assert hasattr(knowflow, "__version__")
    assert knowflow.__version__ == "0.1.0"
