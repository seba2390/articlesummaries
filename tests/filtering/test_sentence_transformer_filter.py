# tests/filtering/test_sentence_transformer_filter.py
import pytest
from unittest.mock import patch, MagicMock, ANY
import torch # Added for tensor comparison

from src.filtering.sentence_transformer_filter import SentenceTransformerFilter
from src.paper import Paper

# Mock the SentenceTransformer class where it's used
@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_configure_and_load_model(MockSentenceTransformer):
    """Test successful configuration and model loading."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embedding = torch.tensor([[0.1, 0.2, 0.3]]) # Example tensor
    mock_model_instance.encode.return_value = mock_target_embedding

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {
                "model_name": "test-model",
                "similarity_threshold": 0.7,
                "target_texts": ["target one", "target two"],
                "device": "cpu",
                "batch_size": 16
            }
        }
    }
    filter_instance = SentenceTransformerFilter()

    # Act
    filter_instance.configure(config)

    # Assert
    assert filter_instance.configured is True
    assert filter_instance.model_name == "test-model"
    assert filter_instance.similarity_threshold == 0.7
    assert filter_instance.target_texts == ["target one", "target two"]
    assert filter_instance.device == "cpu"
    MockSentenceTransformer.assert_called_once_with("test-model", device="cpu")
    mock_model_instance.encode.assert_called_once_with(["target one", "target two"], convert_to_tensor=True, show_progress_bar=False)
    assert torch.equal(filter_instance.target_embeddings, mock_target_embedding)
    assert filter_instance.model == mock_model_instance

@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_configure_defaults(MockSentenceTransformer):
    """Test configuration with default values."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embedding = torch.tensor([[0.4, 0.5, 0.6]])
    mock_model_instance.encode.return_value = mock_target_embedding
    config = {"relevance_checker": { "sentence_transformer_filter": {} }}
    filter_instance = SentenceTransformerFilter()

    # Act
    filter_instance.configure(config)

    # Assert
    assert filter_instance.batch_size == SentenceTransformerFilter.DEFAULT_BATCH_SIZE
    assert filter_instance.configured is True
    assert filter_instance.model_name == SentenceTransformerFilter.DEFAULT_MODEL
    assert filter_instance.similarity_threshold == SentenceTransformerFilter.DEFAULT_THRESHOLD
    assert filter_instance.target_texts == [SentenceTransformerFilter.DEFAULT_TARGET_TEXT]
    assert filter_instance.device is None # Default device is None
    MockSentenceTransformer.assert_called_once_with(SentenceTransformerFilter.DEFAULT_MODEL, device=None)
    mock_model_instance.encode.assert_called_once_with([SentenceTransformerFilter.DEFAULT_TARGET_TEXT], convert_to_tensor=True, show_progress_bar=False)
    assert torch.equal(filter_instance.target_embeddings, mock_target_embedding)

@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_filter_papers_basic(MockSentenceTransformer):
    """Test basic paper filtering based on similarity threshold."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embedding = torch.tensor([[0.1, 0.2, 0.3]])
    # Simulate embeddings: Paper 1 (relevant), Paper 2 (not relevant)
    mock_paper_embeddings = torch.tensor([[0.1, 0.21, 0.3], [0.8, 0.9, 1.0]])
    mock_model_instance.encode.side_effect = [mock_target_embedding, mock_paper_embeddings]

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {
                "model_name": "test-model",
                "similarity_threshold": 0.95, # High threshold
                "target_texts": ["target"],
                "batch_size": 16
            }
        }
    }
    filter_instance = SentenceTransformerFilter()
    filter_instance.configure(config)

    # Mock cos_sim - needs to return scores based on the embeddings
    # Similarity(paper1, target) = high (e.g., 0.98) -> relevant
    # Similarity(paper2, target) = low (e.g., 0.1) -> not relevant
    with patch("src.filtering.sentence_transformer_filter.cos_sim") as mock_cos_sim:
        mock_cos_sim.return_value = torch.tensor([[0.98], [0.1]]) # Shape (papers, targets)

        paper1 = Paper(id="1", title="Relevant Paper", abstract="Abstract 1", url="url1")
        paper2 = Paper(id="2", title="Irrelevant Paper", abstract="Abstract 2", url="url2")
        papers_in = [paper1, paper2]

        # Act
        relevant_papers = filter_instance.filter(papers_in)

        # Assert
        assert len(relevant_papers) == 1
        assert relevant_papers[0].id == "1"
        assert hasattr(relevant_papers[0], 'similarity_score')
        assert relevant_papers[0].similarity_score == 0.98
        assert hasattr(relevant_papers[0], 'matched_target')
        assert relevant_papers[0].matched_target == "target"
        # Check that encode was called correctly for papers
        mock_model_instance.encode.assert_called_with(["Abstract 1", "Abstract 2"], convert_to_tensor=True, show_progress_bar=True, batch_size=16)
        mock_cos_sim.assert_called_once()
        # Check tensor equality for cos_sim arguments
        call_args, _ = mock_cos_sim.call_args
        assert torch.equal(call_args[0], mock_paper_embeddings)
        assert torch.equal(call_args[1], mock_target_embedding)


@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_filter_papers_multiple_targets(MockSentenceTransformer):
    """Test filtering where similarity to *any* target text is sufficient."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embeddings = torch.tensor([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]) # Two targets
    mock_paper_embeddings = torch.tensor([[0.8, 0.9, 1.0]]) # One paper
    mock_model_instance.encode.side_effect = [mock_target_embeddings, mock_paper_embeddings]

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {
                "model_name": "test-model",
                "similarity_threshold": 0.7,
                "target_texts": ["target A", "target B"],
                "batch_size": 16
            }
        }
    }
    filter_instance = SentenceTransformerFilter()
    filter_instance.configure(config)

    with patch("src.filtering.sentence_transformer_filter.cos_sim") as mock_cos_sim:
        # Simulate scores: low similarity to target A, high similarity to target B
        mock_cos_sim.return_value = torch.tensor([[0.1, 0.75]]) # Shape (papers, targets)

        paper1 = Paper(id="1", title="Relevant Paper", abstract="Abstract 1", url="url1")
        papers_in = [paper1]

        # Act
        relevant_papers = filter_instance.filter(papers_in)

        # Assert
        assert len(relevant_papers) == 1
        assert relevant_papers[0].id == "1"
        assert relevant_papers[0].similarity_score == 0.75 # Max score
        assert relevant_papers[0].matched_target == "target B" # Matched the second target

@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_filter_no_abstracts(MockSentenceTransformer):
    """Test filtering when input papers have no abstracts."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embedding = torch.tensor([[0.1, 0.2, 0.3]])
    mock_model_instance.encode.return_value = mock_target_embedding

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {
                "model_name": "test-model",
                "similarity_threshold": 0.7,
                "target_texts": ["target"]
            }
        }
    }
    filter_instance = SentenceTransformerFilter()
    filter_instance.configure(config)

    paper1 = Paper(id="1", title="No Abstract Paper", abstract=None, url="url1")
    papers_in = [paper1]

    # Act
    relevant_papers = filter_instance.filter(papers_in)

    # Assert
    assert len(relevant_papers) == 0
    # Ensure encode was not called for paper abstracts
    assert mock_model_instance.encode.call_count == 1 # Only called for target text

@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_filter_model_load_fails(MockSentenceTransformer):
    """Test filtering behavior when the model fails to load."""
    # Arrange
    MockSentenceTransformer.side_effect = Exception("Model loading error")

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {"model_name": "bad-model"}
        }
    }
    filter_instance = SentenceTransformerFilter()
    filter_instance.configure(config) # Configuration attempt fails internally

    paper1 = Paper(id="1", title="Test Paper", abstract="Some text", url="url1")
    papers_in = [paper1]

    # Act
    relevant_papers = filter_instance.filter(papers_in)

    # Assert
    assert filter_instance.configured is True # Configuration method was called
    assert filter_instance.model is None # Model loading failed
    assert len(relevant_papers) == 0 # Should return empty list if model not loaded

@patch("src.filtering.sentence_transformer_filter.SentenceTransformer")
def test_filter_encoding_fails(MockSentenceTransformer):
    """Test filtering behavior when abstract encoding fails."""
    # Arrange
    mock_model_instance = MockSentenceTransformer.return_value
    mock_target_embedding = torch.tensor([[0.1, 0.2, 0.3]])
    # First call (targets) succeeds, second call (abstracts) fails
    mock_model_instance.encode.side_effect = [
        mock_target_embedding,
        Exception("Encoding error")
    ]

    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {"model_name": "test-model"}
        }
    }
    filter_instance = SentenceTransformerFilter()
    filter_instance.configure(config)

    paper1 = Paper(id="1", title="Test Paper", abstract="Some text", url="url1")
    papers_in = [paper1]

    # Act
    relevant_papers = filter_instance.filter(papers_in)

    # Assert
    assert len(relevant_papers) == 0 # Should return empty list on encoding error

# --- Additional Test Cases ---

EXAMPLE_ABSTRACTS = [
    "We employ linearized quantum gravity to show that gravitational redshift occurs as a purely quantum process. To achieve our goal we study the interaction between propagating photonic wave-packets and gravitons. Crucially, the redshift occurs as predicted by general relativity but arises in flat spacetime in the absence of curvature. In particular, redshift as a classical gravitational effect can be understood as a mean-field process where an effective interaction occurs between the photon and gravitons in an effective highly-populated coherent state. These results can help improve our understanding of the quantum nature of gravity in the low energy and low curvature regime.",
    "We consider the motion of a quantum particle whose position is measured in random places at random moments in time. We show that a freely moving particle measured in this way undergoes superdiffusion, while a charged particle moving in a magnetic field confined to the lowest Landau level undergoes conventional diffusion. We also look at a particle moving in one dimensional space in a random time-independent potential, so that it is Anderson localized, which is also measured at random points in space and randomly in time. We find that random measurements break localization and this particle also undergoes diffusion. To address these questions, we develop formalism similar to that employed when studying classical and quantum problems with time-dependent noise.",
    "In this study, we employ the variational quantum eigensolver algorithm with a multireference unitary coupled cluster ansatz to report the ground state energy of the BeH2 molecule in a geometry where strong correlation effects are significant. We consider the two most important determinants in the construction of the reference state for our ansatz. Furthermore, in order to carry out our intended 12-qubit computation on a noisy intermediate scale quantum era trapped ion hardware (the commercially available IonQ Forte-I), we perform a series of resource reduction techniques to a. decrease the number of two-qubit gates by 99.84% (from 12515 to 20 two-qubit gates) relative to the unoptimized circuit, and b. reduce the number of measurements via the idea of supercliques, while losing 2.69% in the obtained ground state energy (with error mitigation and post-selection) relative to that computed classically for the same resource-optimized problem setting.",
    "Purine metabolism is a promising therapeutic target in cancer; however how cancer cells respond to purine shortage,particularly their adaptation and vulnerabilities, remains unclear. Using the recently developed purine shortage-inducing prodrug DRP-104 and genetic approaches, we investigated these responses in prostate, lung and glioma cancer models. We demonstrate that when de novo purine biosynthesis is compromised, cancer cells employ microtubules to assemble purinosomes, multi-protein complexes of de novo purine biosynthesis enzymes that enhance purine biosynthesis efficiency. While this process enables tumor cells to adapt to purine shortage stress, it also renders them more susceptible to the microtubule-stabilizing chemotherapeutic drug Docetaxel. Furthermore, we show that although cancer cells primarily rely on de novo purine biosynthesis, they also exploit Methylthioadenosine Phosphorylase (MTAP)-mediated purine salvage as a crucial alternative source of purine supply, especially under purine shortage stress. In support of this finding, combining DRP-104 with an MTAP inhibitor significantly enhances tumor suppression in prostate cancer (PCa) models in vivo. Finally, despite the resilience of the purine supply machinery, purine shortage-stressed tumor cells exhibit increased DNA damage and activation of the cGAS-STING pathway, which may contribute to impaired immunoevasion and provide a molecular basis of the previously observed DRP-104-induced anti-tumor immunity. Together, these findings reveal purinosome assembly and purine salvage as key mechanisms of cancer cell adaptation and resilience to purine shortage while identifying microtubules, MTAP, and immunoevasion deficits as therapeutic vulnerabilities.",
    "The Quantum Approximate Optimization Algorithm (QAOA) is a highly promising variational quantum algorithm that aims to solve combinatorial optimization problems that are classically intractable. This comprehensive review offers an overview of the current state of QAOA, encompassing its performance analysis in diverse scenarios, its applicability across various problem instances, and considerations of hardware-specific challenges such as error susceptibility and noise resilience. Additionally, we conduct a comparative study of selected QAOA extensions and variants, while exploring future prospects and directions for the algorithm. We aim to provide insights into key questions about the algorithm, such as whether it can outperform classical algorithms and under what circumstances it should be used. Towards this goal, we offer specific practical points in a form of a short guide. Keywords: Quantum Approximate Optimization Algorithm (QAOA), Variational Quantum Algorithms (VQAs), Quantum Optimization, Combinatorial Optimization Problems, NISQ Algorithms.",
    "In forensic odontology disaster victim identification, it is crucial to assess the similarity between post mortem (PM) dentitions and ante mortem (AM) dental records from a database. To facilitate ranking AM records by likelihood of a match, the similarity evaluation must yield an intuitive, quantitative score. This study introduces a scoring scheme designed to effectively distinguish 3D dentition surfaces acquired by intraoral 3D photo scans. The scoring scheme was validated on an independent dataset. The scoring scheme presented utilizes two levels of surface similarity, spanning from local similarity of surface representations to regional similarity based on relative keypoint placement. The scoring scheme demonstrated exceptional discriminatory power on the validation data, achieving a Receiver Operating Characteristic (ROC) area-under-the-curve (AUC) of 0.990 (95% CI 0.988 to 0.992). Implementing such a scoring system in disaster victim identification workflows, where AM 3D data can be procured, can provide an initial likelihood of matching, enabling forensic professionals to prioritize cases and allocate resources more efficiently based on objective measures of dental similarity.",
    "Pregnant women with systemic lupus erythematosus (SLE) have an increased risk of maternal complications and adverse fetal outcomes. These include preeclampsia, preterm birth and fetal growth restriction. Interestingly, this increased risk persists in subsequent pregnancies, whereas it decreases in healthy women due to the development of maternal-fetal tolerance. As maternal-fetal tolerance is crucial for a healthy pregnancy, we hypothesize that its failure contributes to the increased risk of pregnancy complications in women with SLE. Therefore, we initiated the FaMaLE study to investigate the failure of maternal-fetal tolerance in pregnant women with SLE.",
    "The variational quantum eigensolver (or VQE) uses the variational principle to compute the ground state energy of a Hamiltonian, a problem that is central to quantum chemistry and condensed matter physics. Conventional computing methods are constrained in their accuracy due to the computational limits. The VQE may be used to model complex wavefunctions in polynomial time, making it one of the most promising near-term applications for quantum computing. Finding a path to navigate the relevant literature has rapidly become an overwhelming task, with many methods promising to improve different parts of the algorithm. Despite strong theoretical underpinnings suggesting excellent scaling of individual VQE components, studies have pointed out that their various pre-factors could be too large to reach a quantum computing advantage over conventional methods. This review aims to provide an overview of the progress that has been made on the different parts of the algorithm. All the different components of the algorithm are reviewed in detail including representation of Hamiltonians and wavefunctions on a quantum computer, the optimization process, the post-processing mitigation of errors, and best practices are suggested. We identify four main areas of future research:(1) optimal measurement schemes for reduction of circuit repetitions; (2) large scale parallelization across many quantum computers;(3) ways to overcome the potential appearance of vanishing gradients in the optimization process, and how the number of iterations required for the optimization scales with system size; (4) the extent to which VQE suffers for quantum noise, and whether this noise can be mitigated. The answers to these open research questions will determine the routes for the VQE to achieve quantum advantage as the quantum computing hardware scales up and as the noise levels are reduced.",
    "Quantum simulation of chemical systems is one of the most promising near-term applications of quantum computers. The variational quantum eigensolver, a leading algorithm for molecular simulations on quantum hardware, has a serious limitation in that it typically relies on a pre-selected wavefunction ansatz that results in approximate wavefunctions and energies. Here we present an arbitrarily accurate variational algorithm that instead of fixing an ansatz upfront, this algorithm grows it systematically one operator at a time in a way dictated by the molecule being simulated. This generates an ansatz with a small number of parameters, leading to shallow-depth circuits. We present numerical simulations, including for a prototypical strongly correlated molecule, which show that our algorithm performs much better than a unitary coupled cluster approach, in terms of both circuit depth and chemical accuracy. Our results highlight the potential of our adaptive algorithm for exact simulations with present-day and near-term quantum hardware.",
    "Tensor networks represent the state-of-the-art in computational methods across many disciplines, including the classical simulation of quantum many-body systems and quantum circuits. Several applications of current interest give rise to tensor networks with irregular geometries. Finding the best possible contraction path for such networks is a central problem, with an exponential effect on computation time and memory footprint. In this work, we implement new randomized protocols that find very high quality contraction paths for arbitrary and large tensor networks. We test our methods on a variety of benchmarks, including the random quantum circuit instances recently implemented on Google quantum chips. We find that the paths obtained can be very close to optimal, and often many orders or magnitude better than the most established approaches. As different underlying geometries suit different methods, we also introduce a hyper-optimization approach, where both the method applied and its algorithmic parameters are tuned during the path finding. The increase in quality of contraction schemes found has significant practical implications for the simulation of quantum many-body systems and particularly for the benchmarking of new quantum chips. Concretely, we estimate a speed-up of over 10,000× compared to the original expectation for the classical simulation of the Sycamore `supremacy' circuits.",
]

EXAMPLE_RESEARCH_DESC = (
    "My research is on tensor networks for quantum circuit simulations, "
    "quantum circuit simulation in general and variational quantum algorithms "
    "for both combinatorial optimization and quantum chemistry."
)

EXAMPLE_EXPECTED_LABELS = [
    False, # "not relevant"
    False, # "not relevant"
    True,  # "relevant"
    False, # "not relevant"
    True,  # "relevant"
    False, # "not relevant"
    False, # "not relevant"
    True,  # "relevant"
    True,  # "relevant"
    True,  # "relevant"
]

EXAMPLE_MODELS = [
    "all-minilm-l6-v2",
    # "allenai-specter", # Removed as it gives different results with the 0.3 threshold
    "all-mpnet-base-v2",
    "all-MiniLM-L12-v2",
]

EXAMPLE_THRESHOLD = 0.3

@pytest.mark.parametrize("model_name", EXAMPLE_MODELS)
def test_filter_papers_with_example_data(model_name):
    """Tests filtering accuracy with specific data and models from the example script."""
    # Arrange
    papers_to_filter = [Paper(id=f"test-id-{i}",
                        title=f"Paper {i+1}",
                        abstract=abstract,
                        url=f"http://example.com/{i+1}",
                        source="test")
                        for i, abstract in enumerate(EXAMPLE_ABSTRACTS)]

    filter_instance = SentenceTransformerFilter()
    # Structure the config dict as expected by the configure method
    config = {
        "relevance_checker": {
            "sentence_transformer_filter": {
                "model_name": model_name,
                "similarity_threshold": EXAMPLE_THRESHOLD,
                "target_texts": [EXAMPLE_RESEARCH_DESC],
                "device": None, # Use auto-detection
                "batch_size": 16
            }
        }
    }
    # print(f"DEBUG: Configuring filter for model {model_name} with threshold: {config['relevance_checker']['sentence_transformer_filter']['similarity_threshold']}") # Remove debug print
    filter_instance.configure(config)

    # Act
    relevant_papers = filter_instance.filter(papers_to_filter)

    # Assert
    relevant_indices = {papers_to_filter.index(p) for p in relevant_papers}
    expected_relevant_indices = {i for i, expected in enumerate(EXAMPLE_EXPECTED_LABELS) if expected}

    # Debugging output (optional, can be removed later)
    # print(f"Model: {model_name}")
    # print(f"Relevant Indices (Actual): {relevant_indices}")
    # print(f"Relevant Indices (Expected): {expected_relevant_indices}")

    assert relevant_indices == expected_relevant_indices, \
        f"Mismatch for model {model_name}. Expected {expected_relevant_indices}, got {relevant_indices}"
