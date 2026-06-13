/**
 * Page Manager for Whiteboard
 * Handles multiple pages to prevent canvas overflow
 */
class PageManager {
    constructor() {
        this.pages = [this.createPage()];
        this.currentPageIndex = 0;
        this.maxElementsPerPage = 50;
    }

    createPage() {
        return {
            id: Date.now(),
            elements: [],
            createdAt: new Date()
        };
    }

    getCurrentPage() {
        return this.pages[this.currentPageIndex];
    }

    addElement(element) {
        const currentPage = this.getCurrentPage();

        if (currentPage.elements.length >= this.maxElementsPerPage) {
            // Auto-create new page
            this.pages.push(this.createPage());
            this.currentPageIndex = this.pages.length - 1;
        }

        this.getCurrentPage().elements.push(element);
    }

    nextPage() {
        if (this.currentPageIndex < this.pages.length - 1) {
            this.currentPageIndex++;
            return true;
        }
        return false;
    }

    prevPage() {
        if (this.currentPageIndex > 0) {
            this.currentPageIndex--;
            return true;
        }
        return false;
    }

    clearCurrentPage() {
        this.pages[this.currentPageIndex].elements = [];
    }

    getPageCount() {
        return this.pages.length;
    }

    getCurrentPageIndex() {
        return this.currentPageIndex;
    }
}

module.exports = PageManager;
