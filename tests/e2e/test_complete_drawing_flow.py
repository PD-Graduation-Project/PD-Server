"""
End-to-End Test: Complete Drawing Test Flow

Tests the complete self-administered drawing test workflow:
1. User registration/login
2. Create drawing test
3. Upload both spiral images at once
4. Complete test
5. Verify ML score
"""

import io

from tests.e2e.conftest import E2ETestDataGenerator


class TestCompleteDrawingFlow:
    """
    E2E Test: Complete drawing test flow.

    Flow:
    1. User logs in
    2. User creates drawing test
    3. User uploads both spiral images
    4. User completes test
    5. Verify ML score is calculated
    """

    def test_complete_drawing_flow(
        self,
        e2e_client,
        e2e_user,
    ):
        """
        Execute the complete drawing test flow.
        """
        # ===== STEP 1: User Login =====
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert (
            login_response.status_code == 200
        ), f"Login failed: {login_response.get_json()}"

        tokens = login_response.get_json()

        # ===== STEP 2: Create Group + Drawing Test =====
        group_response = e2e_client.post(
            "/api/groups",
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "application/json",
            },
        )
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "drawing", "group_id": group_id},
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "application/json",
            },
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]
        assert create_response.get_json()["data"]["status"] == "pending"

        # ===== STEP 3: Generate and Upload Both Images =====
        data_generator = E2ETestDataGenerator()
        left_spiral = data_generator.generate_spiral_image(
            width=500, height=500, format="PNG"
        )
        right_spiral = data_generator.generate_spiral_image(
            width=500, height=500, format="PNG"
        )

        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/drawings",
            data={
                "spiral_left": (io.BytesIO(left_spiral), "left_spiral.png"),
                "spiral_right": (io.BytesIO(right_spiral), "right_spiral.png"),
            },
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "multipart/form-data",
            },
        )
        assert (
            upload_response.status_code == 200
        ), f"Upload failed: {upload_response.get_json()}"

        upload_data = upload_response.get_json()["data"]
        assert len(upload_data["inputs"]) == 2

        # Verify status changed to in_progress
        status_response = e2e_client.get(
            f"/api/tests/{test_id}",
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "application/json",
            },
        )
        assert status_response.status_code == 200
        assert status_response.get_json()["data"]["status"] == "in_progress"

        # ===== STEP 4: Complete Test =====
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert (
            complete_response.status_code == 200
        ), f"Complete failed: {complete_response.get_json()}"

        complete_data = complete_response.get_json()["data"]
        assert complete_data["status"] == "completed"
        assert "ml_score" in complete_data
        assert complete_data["ml_score"] is not None
        assert 0.0 <= complete_data["ml_score"] <= 1.0

        # ===== STEP 5: Verify Results =====
        get_response = e2e_client.get(
            f"/api/tests/{test_id}",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert get_response.status_code == 200

        final_data = get_response.get_json()["data"]
        assert final_data["status"] == "completed"
        assert final_data["ml_score"] == complete_data["ml_score"]

    def test_drawing_flow_with_both_images_together(
        self,
        e2e_client,
        e2e_user,
    ):
        """
        Test drawing flow uploading both images in one request.
        """
        # Login
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()

        drawing_auth = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Create group then test
        group_response = e2e_client.post("/api/groups", headers=drawing_auth)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "drawing", "group_id": group_id},
            headers=drawing_auth,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # Generate and upload both images together
        data_generator = E2ETestDataGenerator()
        left_spiral = data_generator.generate_spiral_image(format="PNG")
        right_spiral = data_generator.generate_spiral_image(format="PNG")

        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/drawings",
            data={
                "spiral_left": (io.BytesIO(left_spiral), "left.png"),
                "spiral_right": (io.BytesIO(right_spiral), "right.png"),
            },
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 200

        upload_data = upload_response.get_json()["data"]
        assert len(upload_data["inputs"]) == 2

        # Complete test
        complete_response = e2e_client.post(
            f"/api/tests/{test_id}/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert complete_response.status_code == 200
        assert complete_response.get_json()["data"]["ml_score"] is not None

    def test_drawing_flow_missing_image(
        self,
        e2e_client,
        e2e_user,
    ):
        """
        Test that uploading without both images fails.
        """
        # Login
        login_response = e2e_client.post(
            "/api/auth/login",
            json={"email": e2e_user.email, "password": "testpassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.get_json()

        missing_auth = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        }

        # Create group then test
        group_response = e2e_client.post("/api/groups", headers=missing_auth)
        assert group_response.status_code == 201
        group_id = group_response.get_json()["data"]["id"]

        create_response = e2e_client.post(
            "/api/tests",
            json={"test_type": "drawing", "group_id": group_id},
            headers=missing_auth,
        )
        assert create_response.status_code == 201
        test_id = create_response.get_json()["data"]["id"]

        # Try to upload only left spiral (missing right)
        data_generator = E2ETestDataGenerator()
        left_spiral = data_generator.generate_spiral_image(format="PNG")

        upload_response = e2e_client.post(
            f"/api/tests/{test_id}/drawings",
            data={
                "spiral_left": (io.BytesIO(left_spiral), "left.png"),
            },
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Content-Type": "multipart/form-data",
            },
        )
        assert upload_response.status_code == 400
