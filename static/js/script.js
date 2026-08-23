// Confirm before deleting
function confirmDelete() {
    return confirm("Are you sure you want to delete this product?");
}

// Show success message
function showMessage(message) {
    alert(message);
}

// Confirm logout
function confirmLogout() {
    return confirm("Are you sure you want to logout?");
}

// Validate product form
function validateProductForm() {
    const name = document.getElementById("name");
    const price = document.getElementById("price");
    const quantity = document.getElementById("quantity");

    if (name && name.value.trim() === "") {
        alert("Please enter the product name.");
        return false;
    }

    if (price && price.value <= 0) {
        alert("Please enter a valid price.");
        return false;
    }

    if (quantity && quantity.value < 0) {
        alert("Please enter a valid quantity.");
        return false;
    }

    return true;
}