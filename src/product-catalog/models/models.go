package models

import (
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type Product struct {
	ID            string `gorm:"primaryKey"`
	Name          string
	Description   string
	Picture       string
	ProductPrices []ProductPrice `gorm:"foreignKey:ProductID"`
	Categories    []Category     `gorm:"many2many:product_categories;"`
}

type ProductPrice struct {
	ID        uint   `gorm:"primaryKey"`
	Currency  string `gorm:"uniqueIndex:idx_price"`
	ProductID string `gorm:"uniqueIndex:idx_price"`
	Units     uint
	Nanos     uint `gorm:"default:0"`
}

type Category struct {
	ID   uint `gorm:"primaryKey"`
	Name string
}

type ProductCategory struct {
	ProductID  Product  `gorm:"primaryKey"`
	CategoryID Category `gorm:"primaryKey"`
}

func (m *Product) AfterDelete(tx *gorm.DB) (err error) {
	tx.Clauses(clause.Returning{}).Where("product_id = ?", m.ID).Delete(&ProductPrice{})
	tx.Clauses(clause.Returning{}).Where("product_id = ?", m.ID).Delete(&ProductCategory{})
	return
}

func (m *Category) AfterDelete(tx *gorm.DB) (err error) {
	tx.Clauses(clause.Returning{}).Where("category_id = ?", m.ID).Delete(&ProductCategory{})
	return
}
